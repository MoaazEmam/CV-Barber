from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.config import current_active_user
from app.db.dependencies import get_db
from app.db.models import ApplicationModel, QAResponseModel, User
from app.llm.exceptions import (
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)
from app.api.rate_limit import LLM_USER_LIMITS, limiter
from app.llm.qa import CVQAResponder, fallback_company_queries
from app.llm.scorer import compose_jd
from app.schemas.qa import QAItem, QARequest, QAResponse
from app.schemas.tailored_cv import TailoredCV
from app.services.search import (
    get_company_research,
    lookup_and_append_company_facts,
    search_enabled,
)

router = APIRouter()
logger = structlog.get_logger()


@router.post("/applications/{application_id}/qa", response_model=QAResponse)
@limiter.limit(LLM_USER_LIMITS)
async def answer_questions(
    request: Request,
    application_id: UUID,
    payload: QARequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    if not payload.questions or len(payload.questions) > 10:
        raise HTTPException(status_code=422, detail="Provide between 1 and 10 questions")

    result = await db.execute(
        select(ApplicationModel).where(ApplicationModel.id == application_id)
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    tailored_cv = TailoredCV.model_validate(application.tailored_cv_data)
    responder = CVQAResponder()
    research = await get_company_research(
        db, application.company_name, application.job_title
    )
    effective_jd = compose_jd(application.job_description, application.jd_supplement)
    try:
        qa_result = await responder.answer(
            tailored_cv,
            payload.questions,
            job_description=effective_jd,
            company_research=research,
        )

        # If the model flagged company-fact gaps, fetch them, append to the
        # shared cache, and regenerate once with the enriched research. Lookup
        # queries from this second pass are intentionally ignored (no recursion).
        lookup_queries = list(
            dict.fromkeys(
                a.company_lookup_query for a in qa_result.answers if a.company_lookup_query
            )
        )
        # Backstop: the model sometimes hedges about a missing company fact in
        # prose instead of setting the field — recover those so the search still
        # fires automatically (no need to re-ask the same question).
        if not lookup_queries:
            lookup_queries = fallback_company_queries(
                qa_result.answers, application.company_name
            )
        if lookup_queries and search_enabled():
            enriched = await lookup_and_append_company_facts(
                db, application.company_name, lookup_queries, application.job_title
            )
            if enriched and enriched != research:
                qa_result = await responder.answer(
                    tailored_cv,
                    payload.questions,
                    job_description=effective_jd,
                    company_research=enriched,
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

    for item in qa_result.answers:
        db.add(
            QAResponseModel(
                application_id=application_id,
                question=item.question,
                answer=item.answer,
            )
        )
    await db.commit()

    return qa_result


@router.get("/applications/{application_id}/qa", response_model=QAResponse)
async def list_qa(
    application_id: UUID,
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

    rows = await db.execute(
        select(QAResponseModel)
        .where(QAResponseModel.application_id == application_id)
        .order_by(QAResponseModel.created_at.asc())
    )
    items = [QAItem(question=r.question, answer=r.answer) for r in rows.scalars().all()]
    return QAResponse(answers=items)
