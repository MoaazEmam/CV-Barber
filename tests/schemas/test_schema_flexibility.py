"""Schema robustness: optional bullets/email/field and richer education."""

from app.schemas.base_cv import BaseCV
from app.schemas.cv_blocks import (
    DateRange,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
)


def test_experience_bullets_default_empty():
    entry = ExperienceEntry(title="Engineer", date_range=DateRange(start="2020"))
    assert entry.bullets == []


def test_project_bullets_and_tech_default_empty():
    entry = ProjectEntry(name="Side Project")
    assert entry.bullets == []
    assert entry.tech_stack == []


def test_date_range_start_optional():
    # The LLM commonly emits a dateless entry as date_range={"start": null};
    # this must validate rather than failing the whole parse.
    dr = DateRange(start=None)
    assert dr.start is None
    entry = ProjectEntry(name="Course Project", date_range={"start": None, "end": None})
    assert entry.date_range.start is None


def test_education_field_optional_with_minor_and_honors():
    entry = EducationEntry(
        institution="MIT",
        date_range=DateRange(start="2018", end="2022"),
        minor="Mathematics",
        honors="Magna Cum Laude",
    )
    assert entry.field is None
    assert entry.minor == "Mathematics"
    assert entry.honors == "Magna Cum Laude"


def test_base_cv_email_optional():
    cv = BaseCV(full_name="Jane Doe")
    assert cv.email is None


def test_prose_role_as_single_bullet_is_valid():
    # A paragraph-style role kept as one bullet must validate cleanly.
    entry = ExperienceEntry(
        title="Consultant",
        date_range=DateRange(start="2019", end="2023"),
        bullets=["Advised multiple clients on cloud migration over four years."],
    )
    assert len(entry.bullets) == 1


# --- over-strictness fixes: non-vital data must never fail validation ---


def test_experience_and_education_dateless():
    exp = ExperienceEntry(title="Freelancer")
    assert exp.date_range is None
    exp2 = ExperienceEntry(title="Engineer", date_range=None)
    assert exp2.date_range is None
    edu = EducationEntry(institution="MIT")
    assert edu.date_range is None


def test_date_range_as_bare_string_is_coerced():
    exp = ExperienceEntry(title="Engineer", date_range="Sep 2020 – Mar 2023")
    assert exp.date_range.start == "Sep 2020"
    assert exp.date_range.end == "Mar 2023"
    edu = EducationEntry(institution="MIT", date_range="2018 - 2022")
    assert edu.date_range.start == "2018"
    assert edu.date_range.end == "2022"
    proj = ProjectEntry(name="Thing", date_range="2021 to Present")
    assert proj.date_range.start == "2021"
    assert proj.date_range.end == "Present"
    single = ProjectEntry(name="Thing", date_range="2020")
    assert single.date_range.start == "2020"
    assert single.date_range.end is None
    empty = ProjectEntry(name="Thing", date_range="  ")
    assert empty.date_range is None


def test_bullets_as_bare_string_is_coerced():
    exp = ExperienceEntry(title="Engineer", bullets="Did all the backend work.")
    assert exp.bullets == ["Did all the backend work."]
    proj = ProjectEntry(name="Thing", bullets=None)
    assert proj.bullets == []


def test_skills_flat_list_is_wrapped():
    from app.schemas.master_cv import MasterCV

    cv = MasterCV(full_name="Jane Doe", skills=["Python", "Docker"])
    assert len(cv.skills) == 1
    assert cv.skills[0].category == "Skills"
    assert cv.skills[0].skills == ["Python", "Docker"]
    mixed = MasterCV(
        full_name="Jane Doe",
        skills=[{"category": "Languages", "skills": ["Python"]}, "Docker"],
    )
    assert {c.category for c in mixed.skills} == {"Languages", "Skills"}


def test_skill_category_missing_name_defaults():
    from app.schemas.cv_blocks import SkillCategory

    cat = SkillCategory(skills=["Python"])
    assert cat.category == "Skills"
    cat2 = SkillCategory(category=None, skills="Python")
    assert cat2.category == "Skills"
    assert cat2.skills == ["Python"]


def test_certifications_as_objects_are_coerced():
    from app.schemas.master_cv import MasterCV

    cv = MasterCV(
        full_name="Jane Doe",
        certifications=[
            {"name": "AWS SAA", "issuer": "Amazon", "date": "2023"},
            "CKA",
            {"title": "GCP ACE"},
            {"issuer": "nobody"},
            None,
        ],
    )
    assert [c.name for c in cv.certifications] == ["AWS SAA", "CKA", "GCP ACE"]
    assert cv.certifications[0].issuer == "Amazon"
    assert cv.certifications[0].date == "2023"


def test_duplicate_item_link_pruned_from_top_links():
    """A credential URL attached to a certification must not also linger in the
    top-level links list (the ONE-PLACE rule, enforced in code)."""
    from app.schemas.master_cv import MasterCV

    drive = "https://drive.google.com/file/d/ABC/view"
    cv = MasterCV(
        full_name="Yara",
        links=[{"label": "Portfolio", "url": "https://yara.dev"}, {"url": drive}],
        certifications=[{"name": "Back-End Module", "url": drive}],
    )
    assert [l.url for l in cv.links] == ["https://yara.dev"]
    assert cv.certifications[0].url == drive


def test_links_section_is_folded_not_duplicated():
    """A CV "Links" section must not render twice (header + a LINKS section). Its
    URLs fold into links and dedupe against linkedin/github; mailto/tel are dropped."""
    from app.schemas.master_cv import MasterCV

    cv = MasterCV(
        full_name="Moaaz",
        linkedin="https://www.linkedin.com/in/moaaz",
        github="https://github.com/Moaaz",
        additional_sections=[{"title": "Links", "entries": [
            {"url": "mailto:me@x.com"},
            {"url": "https://www.linkedin.com/in/moaaz"},  # dup of linkedin field
            {"url": "https://github.com/Moaaz"},            # dup of github field
            {"heading": "Portfolio", "url": "https://moaaz.dev"},
        ]}],
    )
    assert all((s.title or "").lower() != "links" for s in cv.additional_sections)
    assert [l.url for l in cv.links] == ["https://moaaz.dev"]


def test_norm_url_dedupes_scheme_and_www_variants():
    from app.schemas.master_cv import MasterCV

    cv = MasterCV(
        full_name="X",
        website="https://example.com",
        links=[{"url": "http://www.example.com/"}],  # same destination, different form
    )
    assert cv.links == []  # pruned as a duplicate of website


def test_combined_award_certificate_title_is_tidied():
    """After certificates are extracted into the certifications field, a leftover
    'Awards & Certificates' section is retitled to just 'Awards'."""
    from app.schemas.master_cv import MasterCV

    cv = MasterCV(
        full_name="Yara",
        certifications=[{"name": "AWS SAA"}],
        additional_sections=[{"title": "AWARDS & CERTIFICATES", "entries": [
            {"heading": "Scholarship"},
        ]}],
    )
    assert cv.additional_sections[0].title == "AWARDS"


def test_certification_link_is_preserved():
    from app.schemas.master_cv import MasterCV

    cv = MasterCV(
        full_name="Jane Doe",
        certifications=[
            {"name": "AWS SAA", "url": "https://credly.com/badge/123"},
            "Scrum Master — https://verify.scrum.org/abc",
        ],
    )
    assert cv.certifications[0].url == "https://credly.com/badge/123"
    assert cv.certifications[1].url == "https://verify.scrum.org/abc"
    assert cv.certifications[1].name == "Scrum Master"


def test_extra_profile_links_are_preserved():
    from app.schemas.master_cv import MasterCV

    cv = MasterCV(
        full_name="Jane Doe",
        links=[
            "https://scholar.google.com/citations?user=abc",
            {"label": "Portfolio", "url": "https://jane.dev"},
            {"name": "X", "href": "https://x.com/jane"},
            {"label": "no url here"},
        ],
    )
    assert [(l.label, l.url) for l in cv.links] == [
        (None, "https://scholar.google.com/citations?user=abc"),
        ("Portfolio", "https://jane.dev"),
        ("X", "https://x.com/jane"),
    ]


def test_full_name_still_required():
    import pytest
    from pydantic import ValidationError
    from app.schemas.master_cv import MasterCV

    with pytest.raises(ValidationError):
        MasterCV(full_name="   ")
    with pytest.raises(ValidationError):
        MasterCV()


def test_scored_entries_tolerate_loose_scores():
    from app.schemas.tailored_cv import ScoredExperienceEntry, ScoredProjectEntry

    e = ScoredExperienceEntry(title="Engineer", relevance_score=8.6)
    assert e.relevance_score == 9
    assert e.relevance_reason == ""
    e2 = ScoredExperienceEntry(title="Engineer", relevance_score="15")
    assert e2.relevance_score == 10
    e3 = ScoredExperienceEntry(title="Engineer")
    assert e3.relevance_score == 5
    p = ScoredProjectEntry(name="Thing", relevance_score=None, relevance_reason=["a", "b"])
    assert p.relevance_score == 5
    assert p.relevance_reason == "a; b"


def test_tailored_cv_job_fields_default_empty():
    from app.schemas.tailored_cv import TailoredCV

    cv = TailoredCV(full_name="Jane Doe")
    assert cv.job_title == ""
    assert cv.company_name == ""


def test_ats_scores_tolerate_loose_shapes():
    import pytest
    from pydantic import ValidationError
    from app.schemas.ats import GeneralATSScore, JobATSScore

    g = GeneralATSScore(score="85.4", strengths=None, improvements="Add keywords")
    assert g.score == 85
    assert g.strengths == []
    assert g.improvements == ["Add keywords"]
    j = JobATSScore(score=72.9)
    assert j.score == 73
    assert j.matched_keywords == []
    with pytest.raises(ValidationError):
        GeneralATSScore(score=None)  # a scoreless ATS result should retry


def test_qa_answer_as_list_is_joined():
    from app.schemas.qa import QAItem

    item = QAItem(question="Why?", answer=["Because", "reasons"])
    assert item.answer == "Because; reasons"
