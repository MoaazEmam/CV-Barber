"""JD enrichment: user-confirmed web search for a fuller/typical job
description when the pasted one is thin. Stateless — the frontend shows a
preview and, if accepted, sends the supplement along in the tailor request."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.models import EnrichJDRequest, EnrichJDResponse, EnrichJDSource
from app.api.rate_limit import SEARCH_USER_LIMITS, limiter
from app.auth.config import current_active_user
from app.db.models import User
from app.services.search import SearchError, enrich_job_description, search_enabled

router = APIRouter()


@router.get("/enrich-jd/enabled")
async def enrich_enabled(current_user: User = Depends(current_active_user)):
    return {"enabled": search_enabled()}


@router.post("/enrich-jd", response_model=EnrichJDResponse)
@limiter.limit(SEARCH_USER_LIMITS)
async def enrich_jd(
    request: Request,
    payload: EnrichJDRequest,
    current_user: User = Depends(current_active_user),
):
    if not search_enabled():
        raise HTTPException(status_code=404, detail="Web search is not enabled.")
    try:
        supplement, sources = await enrich_job_description(
            payload.job_title, payload.company_name
        )
    except SearchError:
        raise HTTPException(
            status_code=502,
            detail="Could not fetch a description for this role. Please try again later.",
        )
    return EnrichJDResponse(
        supplement=supplement,
        sources=[EnrichJDSource(**s) for s in sources],
    )
