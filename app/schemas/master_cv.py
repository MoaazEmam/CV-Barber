from typing import Optional
from pydantic import Field, field_validator
from app.schemas.base_cv import BaseCV
from app.schemas.cv_blocks import (
    AdditionalSection,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    SkillCategory,
    coerce_additional_sections,
)


class MasterCV(BaseCV):
    """
    Full structured CV built once from the uploaded file.
    Saved to disk and reused for every job application.
    """
    summary: Optional[str] = None
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    skills: list[SkillCategory] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    # Non-standard sections (Honors, Languages, Leadership, standalone Coursework…)
    # preserved verbatim so a template that supports them can render them. Never
    # dropped at parse time.
    additional_sections: list[AdditionalSection] = Field(default_factory=list)

    @field_validator("additional_sections", mode="before")
    @classmethod
    def _coerce_additional_sections(cls, v):
        return coerce_additional_sections(v)
