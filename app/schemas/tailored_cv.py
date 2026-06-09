from typing import Optional

from pydantic import Field, field_validator

from app.schemas.base_cv import BaseCV
from app.schemas.cv_blocks import (
    AdditionalSection,
    ExperienceEntry,
    ProjectEntry,
    SkillCategory,
    EducationEntry,
    coerce_additional_sections,
)


class ScoredExperienceEntry(ExperienceEntry):
    """ExperienceEntry with a relevance score attached by the LLM."""
    relevance_score: int = Field(ge=0, le=10)
    relevance_reason: str = Field(description="One sentence why this is relevant")

class ScoredProjectEntry(ProjectEntry):
    """ProjectEntry with a relevance score attached by the LLM."""
    relevance_score: int = Field(ge=0, le=10)
    relevance_reason: str = Field(description="One sentence why this is relevant")

class TailoredCV(BaseCV):
    """
    Filtered, scored, reordered CV for a specific job application.
    Built from MasterCV + job description by the LLM scorer.
    """
    tailored_summary: Optional[str] = None
    experience: list[ScoredExperienceEntry] = Field(default_factory=list)
    projects: list[ScoredProjectEntry] = Field(default_factory=list)
    skills: list[SkillCategory] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications:list[str]=Field(default_factory=list)
    # Non-standard sections carried through from the master CV unchanged (not scored).
    additional_sections: list[AdditionalSection] = Field(default_factory=list)
    job_title: str
    company_name: str

    @field_validator("additional_sections", mode="before")
    @classmethod
    def _coerce_additional_sections(cls, v):
        return coerce_additional_sections(v)
