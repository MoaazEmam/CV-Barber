import pytest

from app.generation.section_filter import apply_section_config
from app.schemas.tailored_cv import TailoredCV


def _make_cv(**overrides) -> TailoredCV:
    data = {
        "full_name": "Test User",
        "email": "test@example.com",
        "tailored_summary": "summary",
        "job_title": "Engineer",
        "company_name": "Acme",
        "experience": [
            {
                "title": "Backend Eng",
                "company": "A",
                "date_range": {"start": "2020"},
                "bullets": ["b"],
                "relevance_score": 8,
                "relevance_reason": "r",
            },
            {
                "title": "Frontend Eng",
                "company": "B",
                "date_range": {"start": "2021"},
                "bullets": ["b"],
                "relevance_score": 6,
                "relevance_reason": "r",
            },
        ],
        "projects": [
            {
                "name": "P1",
                "tech_stack": ["py"],
                "bullets": ["b"],
                "relevance_score": 7,
                "relevance_reason": "r",
            },
            {
                "name": "P2",
                "tech_stack": ["js"],
                "bullets": ["b"],
                "relevance_score": 5,
                "relevance_reason": "r",
            },
        ],
        "skills": [
            {"category": "Languages", "skills": ["Python"]},
            {"category": "Tools", "skills": ["Docker"]},
        ],
        "education": [
            {
                "institution": "MIT",
                "field": "CS",
                "date_range": {"start": "2018", "end": "2022"},
            }
        ],
        "certifications": ["AWS Cert", "GCP Cert"],
    }
    data.update(overrides)
    return TailoredCV.model_validate(data)


class TestApplySectionConfig:
    def test_none_config_returns_cv_unchanged(self):
        cv = _make_cv()
        out = apply_section_config(cv, None)
        assert len(out.experience) == 2
        assert len(out.projects) == 2
        assert len(out.skills) == 2
        assert len(out.education) == 1
        assert out.certifications == ["AWS Cert", "GCP Cert"]

    def test_empty_dict_returns_cv_unchanged(self):
        cv = _make_cv()
        out = apply_section_config(cv, {})
        assert len(out.experience) == 2
        assert len(out.projects) == 2

    def test_disabled_section_is_cleared(self):
        cv = _make_cv()
        out = apply_section_config(
            cv,
            {"experience": {"enabled": False, "subsections": {}}},
        )
        assert out.experience == []
        # other sections untouched
        assert len(out.projects) == 2

    def test_subsection_false_filters_that_entry(self):
        cv = _make_cv()
        out = apply_section_config(
            cv,
            {
                "experience": {
                    "enabled": True,
                    "subsections": {"experience.0": True, "experience.1": False},
                }
            },
        )
        assert len(out.experience) == 1
        assert out.experience[0].title == "Backend Eng"

    def test_missing_subsection_defaults_to_enabled(self):
        cv = _make_cv()
        # Only mark experience.1 as False; experience.0 missing → kept.
        out = apply_section_config(
            cv,
            {
                "experience": {
                    "enabled": True,
                    "subsections": {"experience.1": False},
                }
            },
        )
        assert len(out.experience) == 1
        assert out.experience[0].title == "Backend Eng"

    def test_certifications_disabled_clears_list(self):
        cv = _make_cv()
        out = apply_section_config(
            cv,
            {"certifications": {"enabled": False, "subsections": {}}},
        )
        assert out.certifications == []

    def test_certifications_subsection_filter(self):
        cv = _make_cv()
        out = apply_section_config(
            cv,
            {
                "certifications": {
                    "enabled": True,
                    "subsections": {"certifications.0": False, "certifications.1": True},
                }
            },
        )
        assert out.certifications == ["GCP Cert"]

    def test_multiple_sections_filtered_together(self):
        cv = _make_cv()
        out = apply_section_config(
            cv,
            {
                "experience": {"enabled": False, "subsections": {}},
                "projects": {
                    "enabled": True,
                    "subsections": {"projects.0": False, "projects.1": True},
                },
                "skills": {"enabled": False, "subsections": {}},
            },
        )
        assert out.experience == []
        assert len(out.projects) == 1
        assert out.projects[0].name == "P2"
        assert out.skills == []
        # untouched sections retained
        assert len(out.education) == 1

    def test_enabled_true_with_empty_subsections_keeps_all(self):
        cv = _make_cv()
        out = apply_section_config(
            cv,
            {"projects": {"enabled": True, "subsections": {}}},
        )
        assert len(out.projects) == 2

    def test_returns_a_new_instance(self):
        cv = _make_cv()
        out = apply_section_config(
            cv, {"experience": {"enabled": False, "subsections": {}}}
        )
        # Original CV is not mutated.
        assert len(cv.experience) == 2
        assert out is not cv
