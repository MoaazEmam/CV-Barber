from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import FeedbackCreate, FeedbackRead
from app.api.rate_limit import limiter
from app.auth.config import current_active_user
from app.db.dependencies import get_db
from app.db.models import FeedbackModel, User

router = APIRouter()


def _to_read(row: FeedbackModel) -> FeedbackRead:
    return FeedbackRead(
        id=row.id,
        type=row.type,
        message=row.message,
        page_context=row.page_context,
        status=row.status,
        created_at=row.created_at,
    )


@router.post("/feedback", response_model=FeedbackRead, status_code=201)
@limiter.limit("5/minute")
async def submit_feedback(
    request: Request,
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    row = FeedbackModel(
        user_id=current_user.id,
        type=payload.type,
        message=payload.message,
        page_context=payload.page_context,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_read(row)


@router.get("/feedback", response_model=list[FeedbackRead])
async def list_my_feedback(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    result = await db.execute(
        select(FeedbackModel)
        .where(FeedbackModel.user_id == current_user.id)
        .order_by(FeedbackModel.created_at.desc())
    )
    return [_to_read(row) for row in result.scalars().all()]
