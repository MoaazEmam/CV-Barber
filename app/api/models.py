from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ParseResponse(BaseModel):
    session_id: str
    full_name: str
    experience_count: int
    project_count: int
    skills_count: int
    message: str
    # Non-blocking notices about parse quality (empty sections, missing contact, …).
    warnings: list[str] = Field(default_factory=list)


class TailorRequest(BaseModel):
    session_id: str
    job_title: str
    company_name: str
    job_description: str
    top_n_experience: int = 3
    top_n_projects: int = 5
    # Reordering is always applied; rewriting the summary for this job is opt-out.
    rewrite_summary: bool = True


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
    cover_letter: str | None = None


class MasterCVListItem(BaseModel):
    id: UUID
    full_name: str
    experience_count: int
    project_count: int
    skills_count: int
    created_at: datetime


class MasterCVListResponse(BaseModel):
    master_cvs: list[MasterCVListItem]


# --- Feedback ---

FeedbackType = Literal["suggestion", "bug", "other"]
FeedbackStatus = Literal["open", "resolved"]


class FeedbackCreate(BaseModel):
    type: FeedbackType
    message: str = Field(min_length=3, max_length=5000)
    page_context: str | None = Field(default=None, max_length=200)


class FeedbackRead(BaseModel):
    id: UUID
    type: FeedbackType
    message: str
    page_context: str | None
    status: FeedbackStatus
    created_at: datetime


class AdminFeedbackRead(FeedbackRead):
    user_email: str
    username: str | None


class FeedbackStatusUpdate(BaseModel):
    status: FeedbackStatus


# --- Admin metrics ---

class DayCount(BaseModel):
    date: str  # ISO date "YYYY-MM-DD"
    count: int


class HourCount(BaseModel):
    hour: int  # 0-23
    count: int


class LabelCount(BaseModel):
    label: str
    count: int


class AdminMetrics(BaseModel):
    total_users: int
    verified_users: int
    unverified_users: int
    active_users_7d: int
    active_users_30d: int
    total_master_cvs: int
    total_applications: int
    cover_letters_generated: int
    custom_templates: int
    qa_sets: int
    avg_applications_per_user: float
    open_feedback_count: int
    signups_per_day: list[DayCount]
    activity_per_day: list[DayCount]
    peak_hours: list[HourCount]
    template_popularity: list[LabelCount]
