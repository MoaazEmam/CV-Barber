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
    assert cv.certifications == ["AWS SAA", "CKA", "GCP ACE"]


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
