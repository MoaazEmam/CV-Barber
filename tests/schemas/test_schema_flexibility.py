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
