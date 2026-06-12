from datetime import datetime
from uuid import uuid4

from fastapi_users.db import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
)
from fastapi_users_db_sqlalchemy.generics import GUID
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    __tablename__ = "oauth_account"
    # The base class targets table "user"; ours is "users", so redeclare the FK.
    user_id: Mapped[uuid4] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="cascade"), nullable=False
    )


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    # Nullable: a Google-OAuth user has no username until they pick one
    # (username IS NULL == "needs username", enforced by the frontend).
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(lazy="joined")

    # Case-insensitive uniqueness on username: a functional unique index on
    # lower(username) so "John" and "john" can't both exist. This also serves the
    # case-insensitive login lookup in UserManager.authenticate. (Email is handled
    # case-insensitively by FastAPI Users' get_by_email.)
    __table_args__ = (
        Index("ix_users_username_lower", text("lower(username)"), unique=True),
    )


class EmailVerificationCode(Base):
    """One active 6-digit verification code per user (hashed). Replaced on
    resend; deleted on successful verification."""

    __tablename__ = "email_verification_codes"

    user_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Sends within the current 1-hour window (reset when the window expires).
    send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


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
    # New pipeline cache (per dedup hash): the format-preserving template and the
    # span->role section map produced once by the Tier 1 LLM. template_artifact is
    # a .tex string for PDF inputs, or a JSON-serialised paragraph-index map for DOCX.
    template_artifact: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_map: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
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
    # Chosen output template: "keep_original", "builtin:<id>", or "custom:<uuid>".
    # Null means "use the default for the input format" (see render_dispatch).
    template_id: Mapped[str | None] = mapped_column(String, nullable=True)
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


class FeedbackModel(Base):
    """User-submitted feedback (suggestion / bug / other), reviewed by admins."""

    __tablename__ = "feedback"

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Plain strings (not PG enums) so the SQLite test DB works; values are
    # constrained by the Pydantic Literal types in app/api/models.py.
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # suggestion | bug | other
    message: Mapped[str] = mapped_column(Text, nullable=False)
    page_context: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # open | resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserTemplateModel(Base):
    """A custom CV template uploaded by a user (.html for WeasyPrint or .tex for
    Tectonic). Rendered only in a sandbox. Reusable across the user's applications."""
    __tablename__ = "user_templates"

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False)  # "html" | "tex"
    source: Mapped[str] = mapped_column(Text, nullable=False)
    # SHA-256 over the normalized *original* upload (pre-conversion) — dedup key so
    # the same file isn't stored twice (and re-uploads skip the LLM conversion).
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
