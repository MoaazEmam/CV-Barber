from fastapi import APIRouter, UploadFile, File, Depends, HTTPException

from app.api.dependencies import SessionStore, get_session_store
from app.api.models import ParseResponse
from app.extraction import TextExtractor
from app.llm import (
    CVParser,
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)

router = APIRouter()
extractor = TextExtractor()


@router.post("/parse", response_model=ParseResponse)
async def parse_cv(
    file: UploadFile = File(...),
    store: SessionStore = Depends(get_session_store),
):
    # validate file type
    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(
            status_code=400, detail="Unsupported file type. Upload a PDF or DOCX."
        )

    try:
        file_bytes = await file.read()
        raw_text = extractor.extract_cv_text_from_bytes(file_bytes, file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not extract text: {e}")

    try:
        parser = CVParser()
        master_cv = parser.parse(raw_text)
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

    session_id = store.save_master(master_cv)

    return ParseResponse(
        session_id=session_id,
        full_name=master_cv.full_name,
        experience_count=len(master_cv.experience),
        project_count=len(master_cv.projects),
        skills_count=len(master_cv.skills),
        message=f"CV parsed successfully. Found {len(master_cv.experience)} experience "
        f"entries and {len(master_cv.projects)} projects.",
    )
