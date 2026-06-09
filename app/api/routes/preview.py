from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.render_helpers import render_application, resolve_template
from app.auth.config import current_active_user
from app.db.dependencies import get_db
from app.db.models import ApplicationModel, User

router = APIRouter()
log = structlog.get_logger()


@router.get("/preview/{tailored_id}")
async def preview_cv(
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

    from app.generation.render_dispatch import KEEP_ORIGINAL

    _, _, template_id = await resolve_template(db, application)
    # "Keep original" produces a DOCX, which browsers can't render inline. Tell the
    # client to show a download-to-view note instead of rendering.
    if template_id == KEEP_ORIGINAL:
        return JSONResponse({"preview_unavailable": True, "reason": "docx"})

    try:
        rendered = await render_application(db, application)
    except Exception as e:
        log.warning("preview_render_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to render the preview.")
    return Response(content=rendered.content, media_type=rendered.content_type)
