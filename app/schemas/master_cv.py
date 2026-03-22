from typing import Optional
from pydantic import Field
from app.schemas.base_cv import BaseCV
from app.schemas.cv_blocks import EducationEntry, ExperienceEntry, ProjectEntry, SkillCategory


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