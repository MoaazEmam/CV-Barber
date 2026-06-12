from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.base_cv import BaseCV
from app.schemas.cv_blocks import (
    AdditionalSection,
    ExperienceEntry,
    ProjectEntry,
    SkillCategory,
    EducationEntry,
    coerce_additional_sections,
    coerce_certifications,
    coerce_skills,
)


def _coerce_relevance_score(v):
    """LLMs emit floats, numeric strings, or out-of-range scores; round, clamp,
    and default rather than failing the whole tailoring run."""
    if v is None:
        return 5
    try:
        return min(10, max(0, round(float(v))))
    except (TypeError, ValueError):
        return 5


def _coerce_relevance_reason(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return "; ".join(str(x) for x in v if x is not None)
    return str(v)


class _RelevanceMixin(BaseModel):
    relevance_score: int = Field(default=5, ge=0, le=10)
    relevance_reason: str = Field(
        default="", description="One sentence why this is relevant"
    )

    _coerce_score = field_validator("relevance_score", mode="before")(
        _coerce_relevance_score
    )
    _coerce_reason = field_validator("relevance_reason", mode="before")(
        _coerce_relevance_reason
    )


class ScoredExperienceEntry(ExperienceEntry, _RelevanceMixin):
    """ExperienceEntry with a relevance score attached by the LLM."""

class ScoredProjectEntry(ProjectEntry, _RelevanceMixin):
    """ProjectEntry with a relevance score attached by the LLM."""

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
    # Defaulted: the LLM may omit these; the scorer backfills them from the
    # TailoringConfig (which always carries the user-supplied values).
    job_title: str = ""
    company_name: str = ""

    @field_validator("job_title", "company_name", mode="before")
    @classmethod
    def _coerce_job_fields(cls, v):
        return str(v) if v is not None else ""

    @field_validator("additional_sections", mode="before")
    @classmethod
    def _coerce_additional_sections(cls, v):
        return coerce_additional_sections(v)

    _coerce_skills = field_validator("skills", mode="before")(coerce_skills)
    _coerce_certifications = field_validator("certifications", mode="before")(
        coerce_certifications
    )
