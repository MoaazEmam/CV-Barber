from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.api.dependencies import get_master_cv, save_application
from app.api.models import SectionConfigUpdate, TailorRequest, TailorResponse
from app.api.rate_limit import LLM_USER_LIMITS, limiter
from app.db.models import ApplicationModel
from app.auth.config import current_active_user
from app.db.dependencies import get_db
from app.db.base import AsyncSessionLocal
from app.db.models import User
from app.llm import (
    CVScorer,
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)
from app.schemas.config import TailoringConfig
from app.schemas.tailored_cv import TailoredCV

router = APIRouter()
log = structlog.get_logger()


@router.post("/tailor", response_model=TailorResponse)
@limiter.limit(LLM_USER_LIMITS)
async def tailor_cv(
    request: Request,
    payload: TailorRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    try:
        master_cv_id = UUID(payload.session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found. Please upload your CV again.")

    try:
        master_cv = await get_master_cv(db, master_cv_id, current_user.id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail="Session not found. Please upload your CV again."
        )

    config = TailoringConfig(
        job_title=payload.job_title,
        company_name=payload.company_name,
        top_n_experience=payload.top_n_experience,
        top_n_projects=payload.top_n_projects,
        rewrite_summary=payload.rewrite_summary,
    )

    try:
        scorer = CVScorer()
        log.info(
            "scoring_started",
            job_title=payload.job_title,
            company=payload.company_name,
            master_cv_id=str(master_cv_id),
        )
        tailored_cv = await scorer.score(master_cv, payload.job_description, config)
        log.info(
            "scoring_completed",
            experience=len(tailored_cv.experience),
            projects=len(tailored_cv.projects),
        )
    except LLMAllKeysExhaustedError:
        raise HTTPException(
            status_code=503,
            detail="Daily usage limit reached. The service resets at midnight.",
        )
    except LLMRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=f"Service is busy. Please try again in {e.retry_after_seconds} seconds.",
        )
    except LLMValidationError as e:
        log.warning("cv_tailor_validation_failed", error=str(e))
        raise HTTPException(
            status_code=422,
            detail=(
                "We couldn't reliably tailor your CV for this job. Please try again "
                "in a moment."
            ),
        )

    tailored_id = await save_application(
        db,
        tailored_cv,
        master_cv_id,
        payload.job_title,
        payload.company_name,
        payload.job_description,
        user_id=current_user.id,
    )
    log.info("application_saved", application_id=str(tailored_id))

    # Auto-trigger job ATS score as a background task with a fresh DB session.
    async def _run_job_ats(app_id: UUID, tailored_dump: dict, job_description: str):
        from app.llm.ats_scorer import ATSScorer
        from app.schemas.tailored_cv import TailoredCV as _TailoredCV

        try:
            tailored = _TailoredCV.model_validate(tailored_dump)
            scorer_bg = ATSScorer()
            ats_result = await scorer_bg.score_job(tailored, job_description)
        except Exception as e:
            log.warning("auto_job_ats_failed", error=str(e))
            return
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ApplicationModel).where(ApplicationModel.id == app_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return
            row.job_match_score = ats_result.score
            row.job_improvement_points = {
                "improvements": ats_result.improvements,
                "matched_keywords": ats_result.matched_keywords,
                "missing_keywords": ats_result.missing_keywords,
            }
            await session.commit()

    background_tasks.add_task(
        _run_job_ats, tailored_id, tailored_cv.model_dump(), payload.job_description
    )

    scores = [
        {
            "name": e.title,
            "type": "experience",
            "score": e.relevance_score,
            "reason": e.relevance_reason,
        }
        for e in tailored_cv.experience
    ] + [
        {
            "name": p.name,
            "type": "project",
            "score": p.relevance_score,
            "reason": p.relevance_reason,
        }
        for p in tailored_cv.projects
    ]

    return TailorResponse(
        session_id=payload.session_id,
        tailored_session_id=str(tailored_id),
        full_name=tailored_cv.full_name,
        company_name=tailored_cv.company_name,
        job_title=tailored_cv.job_title,
        experience_count=len(tailored_cv.experience),
        project_count=len(tailored_cv.projects),
        tailored_summary=tailored_cv.tailored_summary,
        scores=scores,
    )


@router.get("/download/{tailored_id}")
async def download_cv(
    tailored_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    application = await db.scalar(
        select(ApplicationModel).where(ApplicationModel.id == tailored_id)
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Tailored CV not found.")
    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Output format is decided by the chosen template (PDF for any template, DOCX
    # only for "keep original"); resolved + rendered by render_application.
    from app.api.render_helpers import render_application
    from app.generation.render_dispatch import output_filename

    try:
        rendered = await render_application(db, application)
    except Exception as e:
        log.warning("download_render_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to render the tailored CV.")

    tailored_cv = TailoredCV.model_validate(application.tailored_cv_data)
    filename = output_filename(tailored_cv, rendered.extension)
    return Response(
        content=rendered.content,
        media_type=rendered.content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.patch("/applications/{application_id}/sections")
async def update_section_config(
    application_id: UUID,
    payload: SectionConfigUpdate,
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
    application.section_config = payload.section_config
    await db.commit()
    return {"ok": True}
