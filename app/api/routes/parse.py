import hashlib
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import save_master_cv
from app.api.models import ParseResponse
from app.api.rate_limit import LLM_USER_LIMITS, limiter
from app.auth.config import current_active_user
from app.db.base import AsyncSessionLocal
from app.db.dependencies import get_db
from app.db.models import MasterCVModel, User
from app.extraction import TextExtractor
from app.llm import (
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)

router = APIRouter()
extractor = TextExtractor()
log = structlog.get_logger()


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — generous for image-heavy CVs

# A genuine CV extracts to thousands of characters. Below this, extraction
# (including OCR for scans) effectively failed — fail loudly with a clear message
# instead of feeding empty text to the LLM and producing a junk CV.
MIN_CV_TEXT_CHARS = 50


def _parse_warnings(
    full_name: str | None,
    email: str | None,
    experience_count: int,
    project_count: int,
    skills_count: int,
) -> list[str]:
    """Non-blocking notices surfaced to the user when a parse looks incomplete."""
    warnings: list[str] = []
    if experience_count == 0 and project_count == 0:
        warnings.append(
            "No work experience or projects were detected — the file's layout may "
            "not have parsed cleanly."
        )
    if not full_name or not email:
        warnings.append(
            "We couldn't confidently detect your name or email — please check the result."
        )
    if skills_count == 0:
        warnings.append("No skills were detected.")
    return warnings


@router.post("/parse", response_model=ParseResponse)
@limiter.limit(LLM_USER_LIMITS)
async def parse_cv(
    request: Request,
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

    # Read at most MAX_UPLOAD_BYTES + 1 so an oversized file is rejected without
    # pulling gigabytes into memory.
    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail="File too large. Maximum upload size is 10 MB."
        )

    try:
        log.info("cv_extraction_started", filename=file.filename, size=len(file_bytes))
        raw_text = extractor.extract_cv_text_from_bytes(file_bytes, file.filename)
        log.info("cv_extraction_completed", chars=len(raw_text))
    except Exception as e:
        log.warning("cv_extraction_failed", filename=file.filename, error=str(e))
        raise HTTPException(
            status_code=422, detail="Could not extract text from the file."
        )

    if len(raw_text.strip()) < MIN_CV_TEXT_CHARS:
        log.warning(
            "cv_text_too_short", filename=file.filename, chars=len(raw_text.strip())
        )
        raise HTTPException(
            status_code=422,
            detail=(
                "We couldn't read any text from this file — it may be a scanned "
                "image or empty. Try uploading a text-based PDF or DOCX."
            ),
        )

    normalized = " ".join(raw_text.split())
    text_hash = hashlib.sha256(normalized.encode()).hexdigest()

    existing = await db.scalar(
        select(MasterCVModel).where(
            MasterCVModel.user_id == current_user.id,
            MasterCVModel.text_hash == text_hash,
        )
    )
    if existing:
        data = existing.parsed_data or {}
        log.info("duplicate_cv_detected", user_id=str(current_user.id), master_cv_id=str(existing.id))
        return ParseResponse(
            session_id=str(existing.id),
            full_name=data.get("full_name", ""),
            experience_count=len(data.get("experience", [])),
            project_count=len(data.get("projects", [])),
            skills_count=len(data.get("skills", [])),
            message="Existing CV matched — no re-upload needed.",
            warnings=_parse_warnings(
                data.get("full_name"),
                data.get("email"),
                len(data.get("experience", [])),
                len(data.get("projects", [])),
                len(data.get("skills", [])),
            ),
        )

    file_type = "pdf" if file.filename.lower().endswith(".pdf") else "docx"
    template_artifact: str | None = None
    section_map: dict | None = None

    try:
        from app.pipeline.pipeline import run_parse

        log.info("pipeline_parse_started", fmt=file_type)
        result = await run_parse(file_bytes, file_type, raw_text)
        master_cv = result.master_cv
        template_artifact = result.template_artifact
        section_map = result.section_map
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
        # Log the raw validation detail for debugging, but never leak the pydantic
        # error dump to the user — surface a clean, actionable message instead.
        log.warning("cv_parse_validation_failed", error=str(e))
        raise HTTPException(
            status_code=422,
            detail=(
                "We couldn't extract enough information from your CV (e.g. a name "
                "or section headings we can recognize). Please try again, or "
                "upload a different version of the file."
            ),
        )

    session_id: UUID = await save_master_cv(
        db,
        master_cv,
        file_bytes,
        file_type,
        user_id=current_user.id,
        text_hash=text_hash,
        template_artifact=template_artifact,
        section_map=section_map,
    )

    # Auto-trigger general ATS score with a fresh DB session.
    async def _run_general_ats(master_cv_id: UUID, master_dump: dict):
        from app.llm.ats_scorer import ATSScorer
        from app.llm.client_factory import LLMClientFactory
        from app.schemas.master_cv import MasterCV as _MasterCV

        try:
            mcv = _MasterCV.model_validate(master_dump)
            scorer = ATSScorer(client=LLMClientFactory.create("background"))
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
        warnings=_parse_warnings(
            master_cv.full_name,
            master_cv.email,
            len(master_cv.experience),
            len(master_cv.projects),
            len(master_cv.skills),
        ),
    )
