from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.config import current_active_user
from app.db.base import AsyncSessionLocal
from app.db.dependencies import get_db
from app.db.models import ApplicationModel, MasterCVModel, User
from app.llm.ats_scorer import ATSScorer
from app.llm.exceptions import (
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)
from app.schemas.ats import GeneralATSScore, JobATSScore
from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV

router = APIRouter()
logger = structlog.get_logger()


async def _persist_general_score(master_cv_id: UUID, score: int, strengths: list[str], improvements: list[str]):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MasterCVModel).where(MasterCVModel.id == master_cv_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.general_ats_score = score
        row.ats_improvement_points = {"improvements": improvements, "strengths": strengths}
        await session.commit()


async def _persist_job_score(application_id: UUID, score: int, matched: list[str], missing: list[str], improvements: list[str]):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ApplicationModel).where(ApplicationModel.id == application_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.job_match_score = score
        row.job_improvement_points = {
            "improvements": improvements,
            "matched_keywords": matched,
            "missing_keywords": missing,
        }
        await session.commit()


@router.post("/cv/{master_cv_id}/ats/general", response_model=GeneralATSScore)
async def score_general_ats(
    master_cv_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    result = await db.execute(
        select(MasterCVModel).where(MasterCVModel.id == master_cv_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="CV not found")
    if row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    master_cv = MasterCV.model_validate(row.parsed_data)
    scorer = ATSScorer()
    try:
        ats_result = await scorer.score_general(master_cv)
    except LLMAllKeysExhaustedError:
        raise HTTPException(status_code=503, detail="Daily usage limit reached.")
    except LLMRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=f"Service is busy. Please try again in {e.retry_after_seconds} seconds.",
        )
    except LLMValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    background_tasks.add_task(
        _persist_general_score,
        master_cv_id,
        ats_result.score,
        ats_result.strengths,
        ats_result.improvements,
    )
    return ats_result


@router.post("/applications/{application_id}/ats/job", response_model=JobATSScore)
async def score_job_ats(
    application_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    result = await db.execute(
        select(ApplicationModel).where(ApplicationModel.id == application_id)
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    tailored_cv = TailoredCV.model_validate(application.tailored_cv_data)
    scorer = ATSScorer()
    try:
        ats_result = await scorer.score_job(tailored_cv, application.job_description)
    except LLMAllKeysExhaustedError:
        raise HTTPException(status_code=503, detail="Daily usage limit reached.")
    except LLMRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=f"Service is busy. Please try again in {e.retry_after_seconds} seconds.",
        )
    except LLMValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    background_tasks.add_task(
        _persist_job_score,
        application_id,
        ats_result.score,
        ats_result.matched_keywords,
        ats_result.missing_keywords,
        ats_result.improvements,
    )
    return ats_result
