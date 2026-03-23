from pydantic import BaseModel
from typing import Optional


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