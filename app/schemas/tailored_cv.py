from typing import Optional

from pydantic import Field

from app.schemas.base_cv import BaseCV
from app.schemas.cv_blocks import ExperienceEntry, ProjectEntry, SkillCategory, EducationEntry


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
    job_title: str
    company_name: str