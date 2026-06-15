from typing import Optional
from pydantic import Field, field_validator, model_validator
from app.schemas.base_cv import BaseCV
from app.schemas.cv_blocks import (
    AdditionalSection,
    CertificationEntry,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    SkillCategory,
    coerce_additional_sections,
    coerce_certifications,
    coerce_skills,
    fold_link_sections_into_links,
    prune_duplicate_links,
    tidy_combined_section_titles,
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
    certifications: list[CertificationEntry] = Field(default_factory=list)
    # Non-standard sections (Honors, Languages, Leadership, standalone Coursework…)
    # preserved verbatim so a template that supports them can render them. Never
    # dropped at parse time.
    additional_sections: list[AdditionalSection] = Field(default_factory=list)

    @field_validator("additional_sections", mode="before")
    @classmethod
    def _coerce_additional_sections(cls, v):
        return coerce_additional_sections(v)

    _coerce_skills = field_validator("skills", mode="before")(coerce_skills)
    _coerce_certifications = field_validator("certifications", mode="before")(
        coerce_certifications
    )

    @model_validator(mode="after")
    def _clean_cross_field(self):
        # Enforce the ONE-PLACE rule deterministically, regardless of the LLM: fold
        # a "Links"/"Social" section into the links field, drop links duplicated onto
        # items/contact fields, and retitle combined sections whose certificates were
        # extracted into the certifications field.
        return tidy_combined_section_titles(
            prune_duplicate_links(fold_link_sections_into_links(self))
        )
