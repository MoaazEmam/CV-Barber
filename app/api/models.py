from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ParseResponse(BaseModel):
    session_id: str
    full_name: str
    experience_count: int
    project_count: int
    skills_count: int
    message: str


class TailorRequest(BaseModel):
    session_id: str
    job_title: str
    company_name: str
    job_description: str
    top_n_experience: int = 3
    top_n_projects: int = 5


class TailorResponse(BaseModel):
    session_id: str
    tailored_session_id: str
    full_name: str
    company_name: str
    job_title: str
    experience_count: int
    project_count: int
    tailored_summary: Optional[str] = None
    scores: list[dict]


class ApplicationSummary(BaseModel):
    id: UUID
    job_title: str
    company_name: str
    created_at: datetime
    job_match_score: int | None


class HistoryResponse(BaseModel):
    applications: list[ApplicationSummary]


class SubSection(BaseModel):
    key: str
    label: str
    enabled: bool


class Section(BaseModel):
    key: str
    label: str
    enabled: bool
    subsections: list[SubSection]


class CVStructureResponse(BaseModel):
    master_cv_id: UUID
    sections: list[Section]


class SectionConfigUpdate(BaseModel):
    section_config: dict


class ApplicationDetail(BaseModel):
    id: UUID
    master_cv_id: UUID
    job_title: str
    company_name: str
    job_description: str
    created_at: datetime
    tailored_cv_data: dict
    job_match_score: int | None
    job_improvement_points: dict | None
    general_ats_score: int | None
    ats_improvement_points: dict | None
    section_config: dict | None
