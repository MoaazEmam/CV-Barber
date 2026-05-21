from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.auth.config import current_active_user
from app.db.dependencies import get_db
from app.db.models import ApplicationModel, User
from app.generation.section_filter import apply_section_config
from app.schemas.tailored_cv import TailoredCV

router = APIRouter()

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "generation" / "templates"


@router.get("/preview/{tailored_id}", response_class=HTMLResponse)
async def preview_cv(
    tailored_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    result = await db.execute(
        select(ApplicationModel).where(ApplicationModel.id == tailored_id)
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise HTTPException(status_code=404, detail="Tailored CV not found.")
    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    tailored_cv = TailoredCV.model_validate(application.tailored_cv_data)
    tailored_cv = apply_section_config(tailored_cv, application.section_config)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("cv.html")
    html = template.render(cv=tailored_cv)
    return HTMLResponse(content=html)
