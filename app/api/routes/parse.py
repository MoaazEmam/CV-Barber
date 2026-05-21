from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import save_master_cv
from app.api.models import ParseResponse
from app.auth.config import current_active_user
from app.db.base import AsyncSessionLocal
from app.db.dependencies import get_db
from app.db.models import MasterCVModel, User
from app.extraction import TextExtractor
from app.llm import (
    CVParser,
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)

router = APIRouter()
extractor = TextExtractor()
log = structlog.get_logger()


@router.post("/parse", response_model=ParseResponse)
async def parse_cv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    # validate file type
    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(
            status_code=400, detail="Unsupported file type. Upload a PDF or DOCX."
        )

    try:
        file_bytes = await file.read()
        log.info("cv_extraction_started", filename=file.filename, size=len(file_bytes))
        raw_text = extractor.extract_cv_text_from_bytes(file_bytes, file.filename)
        log.info("cv_extraction_completed", chars=len(raw_text))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not extract text: {e}")

    try:
        parser = CVParser()
        log.info("llm_parse_started")
        master_cv = await parser.parse(raw_text)
        log.info(
            "llm_parse_completed",
            experience=len(master_cv.experience),
            projects=len(master_cv.projects),
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
        raise HTTPException(status_code=422, detail=str(e))

    file_type = "pdf" if file.filename.lower().endswith(".pdf") else "docx"
    session_id: UUID = await save_master_cv(
        db, master_cv, file_bytes, file_type, user_id=current_user.id
    )

    # Auto-trigger general ATS score with a fresh DB session.
    async def _run_general_ats(master_cv_id: UUID, master_dump: dict):
        from app.llm.ats_scorer import ATSScorer
        from app.schemas.master_cv import MasterCV as _MasterCV

        try:
            mcv = _MasterCV.model_validate(master_dump)
            scorer = ATSScorer()
            ats_result = await scorer.score_general(mcv)
        except Exception as e:
            log.warning("auto_general_ats_failed", error=str(e))
            return
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MasterCVModel).where(MasterCVModel.id == master_cv_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return
            row.general_ats_score = ats_result.score
            row.ats_improvement_points = {
                "improvements": ats_result.improvements,
                "strengths": ats_result.strengths,
            }
            await session.commit()

    background_tasks.add_task(_run_general_ats, session_id, master_cv.model_dump())

    return ParseResponse(
        session_id=str(session_id),
        full_name=master_cv.full_name,
        experience_count=len(master_cv.experience),
        project_count=len(master_cv.projects),
        skills_count=len(master_cv.skills),
        message=f"CV parsed successfully. Found {len(master_cv.experience)} experience "
        f"entries and {len(master_cv.projects)} projects.",
    )
