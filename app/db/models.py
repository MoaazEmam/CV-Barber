from datetime import datetime
from uuid import uuid4

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Case-insensitive uniqueness on username: a functional unique index on
    # lower(username) so "John" and "john" can't both exist. This also serves the
    # case-insensitive login lookup in UserManager.authenticate. (Email is handled
    # case-insensitively by FastAPI Users' get_by_email.)
    __table_args__ = (
        Index("ix_users_username_lower", text("lower(username)"), unique=True),
    )


class MasterCVModel(Base):
    __tablename__ = "master_cvs"

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    raw_file: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    parsed_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    general_ats_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ats_improvement_points: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApplicationModel(Base):
    __tablename__ = "applications"

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    master_cv_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("master_cvs.id"), nullable=False, index=True
    )
    job_title: Mapped[str] = mapped_column(String, nullable=False)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    tailored_cv_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    section_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    job_match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_improvement_points: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QAResponseModel(Base):
    __tablename__ = "qa_responses"

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
