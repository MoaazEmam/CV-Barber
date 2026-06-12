"""Superuser-only admin endpoints: usage metrics + feedback review.

Aggregations stay SQLite-portable (the test DB): scalar counts in SQL, but
day/hour bucketing is done in Python over the last-30-days created_at values
instead of dialect-specific date_trunc/extract.
"""

from collections import Counter
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import (
    AdminFeedbackRead,
    AdminMetrics,
    DayCount,
    FeedbackStatusUpdate,
    HourCount,
    LabelCount,
)
from app.auth.config import current_superuser
from app.db.dependencies import get_db
from app.db.models import (
    ApplicationModel,
    FeedbackModel,
    MasterCVModel,
    QAResponseModel,
    User,
    UserTemplateModel,
)

router = APIRouter(prefix="/admin")


async def _count(db: AsyncSession, stmt) -> int:
    return (await db.execute(stmt)).scalar_one()


async def _active_users(db: AsyncSession, cutoff: datetime) -> int:
    """Users with any activity (CV upload or tailoring) since the cutoff."""
    app_ids = (
        await db.execute(
            select(ApplicationModel.user_id)
            .where(ApplicationModel.created_at >= cutoff)
            .distinct()
        )
    ).scalars().all()
    cv_ids = (
        await db.execute(
            select(MasterCVModel.user_id)
            .where(MasterCVModel.created_at >= cutoff)
            .distinct()
        )
    ).scalars().all()
    return len(set(app_ids) | set(cv_ids))


def _day_series(timestamps: list[datetime], start: datetime, days: int) -> list[DayCount]:
    counts = Counter(ts.date().isoformat() for ts in timestamps)
    return [
        DayCount(date=(start + timedelta(days=i)).date().isoformat(),
                 count=counts.get((start + timedelta(days=i)).date().isoformat(), 0))
        for i in range(days)
    ]


@router.get("/metrics", response_model=AdminMetrics)
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(current_superuser),
):
    now = datetime.utcnow()
    cutoff_30d = now - timedelta(days=30)
    window_start = now - timedelta(days=29)  # 30 buckets including today

    total_users = await _count(db, select(func.count()).select_from(User))
    verified_users = await _count(
        db, select(func.count()).select_from(User).where(User.is_verified == True)  # noqa: E712
    )
    total_master_cvs = await _count(db, select(func.count()).select_from(MasterCVModel))
    total_applications = await _count(db, select(func.count()).select_from(ApplicationModel))
    cover_letters = await _count(db, select(func.count(ApplicationModel.cover_letter)))
    custom_templates = await _count(db, select(func.count()).select_from(UserTemplateModel))
    qa_sets = await _count(db, select(func.count(func.distinct(QAResponseModel.application_id))))
    open_feedback = await _count(
        db, select(func.count()).select_from(FeedbackModel).where(FeedbackModel.status == "open")
    )

    signup_ts = (
        await db.execute(select(User.created_at).where(User.created_at >= cutoff_30d))
    ).scalars().all()
    app_ts = (
        await db.execute(
            select(ApplicationModel.created_at).where(ApplicationModel.created_at >= cutoff_30d)
        )
    ).scalars().all()
    cv_ts = (
        await db.execute(
            select(MasterCVModel.created_at).where(MasterCVModel.created_at >= cutoff_30d)
        )
    ).scalars().all()

    activity_ts = app_ts + cv_ts
    hour_counts = Counter(ts.hour for ts in activity_ts)

    template_rows = (
        await db.execute(
            select(ApplicationModel.template_id, func.count())
            .group_by(ApplicationModel.template_id)
        )
    ).all()
    template_popularity = sorted(
        (LabelCount(label=tid or "default", count=cnt) for tid, cnt in template_rows),
        key=lambda x: -x.count,
    )

    return AdminMetrics(
        total_users=total_users,
        verified_users=verified_users,
        unverified_users=total_users - verified_users,
        active_users_7d=await _active_users(db, now - timedelta(days=7)),
        active_users_30d=await _active_users(db, cutoff_30d),
        total_master_cvs=total_master_cvs,
        total_applications=total_applications,
        cover_letters_generated=cover_letters,
        custom_templates=custom_templates,
        qa_sets=qa_sets,
        avg_applications_per_user=round(total_applications / max(total_users, 1), 2),
        open_feedback_count=open_feedback,
        signups_per_day=_day_series(signup_ts, window_start, 30),
        activity_per_day=_day_series(activity_ts, window_start, 30),
        peak_hours=[HourCount(hour=h, count=hour_counts.get(h, 0)) for h in range(24)],
        template_popularity=template_popularity,
    )


def _to_admin_read(row: FeedbackModel, user: User) -> AdminFeedbackRead:
    return AdminFeedbackRead(
        id=row.id,
        type=row.type,
        message=row.message,
        page_context=row.page_context,
        status=row.status,
        created_at=row.created_at,
        user_email=user.email,
        username=user.username,
    )


@router.get("/feedback", response_model=list[AdminFeedbackRead])
async def list_feedback(
    status: str | None = Query(default=None, pattern="^(open|resolved)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(current_superuser),
):
    # No SQL join: feedback.user_id (PG UUID) and users.id (fastapi-users GUID)
    # serialize differently on the SQLite test DB, so the users are fetched
    # separately and matched in Python.
    stmt = select(FeedbackModel).order_by(FeedbackModel.created_at.desc())
    if status:
        stmt = stmt.where(FeedbackModel.status == status)
    stmt = stmt.limit(limit).offset(offset)
    items = (await db.execute(stmt)).scalars().all()
    user_ids = {fb.user_id for fb in items}
    users = (
        (await db.execute(select(User).where(User.id.in_(user_ids)))).unique().scalars().all()
        if user_ids
        else []
    )
    by_id = {u.id: u for u in users}
    return [_to_admin_read(fb, by_id[fb.user_id]) for fb in items]


@router.patch("/feedback/{feedback_id}", response_model=AdminFeedbackRead)
async def update_feedback_status(
    feedback_id: UUID,
    payload: FeedbackStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(current_superuser),
):
    fb = (
        await db.execute(select(FeedbackModel).where(FeedbackModel.id == feedback_id))
    ).scalar_one_or_none()
    if fb is None:
        raise HTTPException(status_code=404, detail="Not found")
    user = (
        await db.execute(select(User).where(User.id == fb.user_id))
    ).unique().scalar_one()
    fb.status = payload.status
    await db.commit()
    await db.refresh(fb)
    return _to_admin_read(fb, user)
