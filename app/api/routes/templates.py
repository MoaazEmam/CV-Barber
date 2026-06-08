"""Custom template upload + per-application template selection.

- POST   /api/templates                              upload a .html/.tex template (sandbox test-render, then store)
- GET    /api/templates                              list the user's uploaded templates
- DELETE /api/templates/{template_id}                delete one
- GET    /api/applications/{id}/template-options     choices allowed for that application + the selected one
- PATCH  /api/applications/{id}/template             set the chosen template

User templates are rendered ONLY in a sandbox (see render_dispatch): Jinja
SandboxedEnvironment, WeasyPrint with a blocked url_fetcher, Tectonic --untrusted.
"""
import re
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    create_user_template,
    delete_user_template,
    get_user_template,
    list_user_templates,
)
from app.api.rate_limit import LLM_USER_LIMITS, limiter
from app.auth.config import current_active_user
from app.db.dependencies import get_db
from app.db.models import ApplicationModel, MasterCVModel, User
from app.generation.template_registry import TEMPLATES_DIR

router = APIRouter()
log = structlog.get_logger()

MAX_TEMPLATE_BYTES = 256 * 1024
MAX_TEMPLATES_PER_USER = 25
_EXT_FORMAT = {".html": "html", ".htm": "html", ".tex": "tex"}
_EXAMPLE_FILES = {"tex": "cv_example.tex", "html": "cv_example.html"}
# A template that fills with CV data references a `cv.*` field inside a placeholder.
_PLACEHOLDER_RE = re.compile(r"(\\VAR\{|\{\{)[^{}]*\bcv\b")


class TemplateSelect(BaseModel):
    template_id: str


def _format_for(filename: str) -> str | None:
    lower = (filename or "").lower()
    for ext, fmt in _EXT_FORMAT.items():
        if lower.endswith(ext):
            return fmt
    return None


def _custom_id(row) -> str:
    return f"custom:{row.id}"


@router.post("/templates")
@limiter.limit(LLM_USER_LIMITS)
async def upload_template(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    fmt = _format_for(file.filename)
    if fmt is None:
        raise HTTPException(status_code=400, detail="Upload a .html or .tex template file.")

    data = await file.read(MAX_TEMPLATE_BYTES + 1)
    if len(data) > MAX_TEMPLATE_BYTES:
        raise HTTPException(status_code=413, detail="Template too large. Maximum size is 256 KB.")
    source = data.decode("utf-8", errors="replace")

    existing = await list_user_templates(db, current_user.id)
    if len(existing) >= MAX_TEMPLATES_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"You can store at most {MAX_TEMPLATES_PER_USER} templates. Delete one first.",
        )

    # Sandbox test-render with a sample CV before storing — proves it compiles and
    # rejects anything malicious/broken. Run in a threadpool (WeasyPrint/Tectonic block).
    from app.generation.render_dispatch import (
        TemplateRenderError,
        _render_custom_html,
        _render_custom_tex,
        sample_tailored_cv,
    )

    renderer = _render_custom_tex if fmt == "tex" else _render_custom_html
    try:
        await run_in_threadpool(renderer, source, sample_tailored_cv())
    except TemplateRenderError as e:
        log.warning("custom_template_rejected", error=str(e), fmt=fmt)
        raise HTTPException(
            status_code=422,
            detail="That template failed to render. Check the template and try again.",
        )

    name = file.filename or f"template.{fmt}"
    template_uuid = await create_user_template(db, current_user.id, name, fmt, source)
    log.info("custom_template_saved", template_id=str(template_uuid), fmt=fmt)

    # Warn (don't block) if the template has no placeholders — it'll render the same
    # content for every job because nothing gets filled in.
    warning = None
    if not _PLACEHOLDER_RE.search(source):
        warning = (
            "This template has no placeholders (e.g. \\VAR{ cv.full_name } for .tex or "
            "{{ cv.full_name }} for .html), so it will render the same content for every "
            "job. Download the example template to see the expected format."
        )
    return {
        "id": f"custom:{template_uuid}", "template_id": str(template_uuid),
        "name": name, "format": fmt, "warning": warning,
    }


@router.get("/templates/example")
async def example_template(
    format: str = "tex",
    current_user: User = Depends(current_active_user),
):
    fname = _EXAMPLE_FILES.get(format)
    if fname is None:
        raise HTTPException(status_code=400, detail="format must be 'tex' or 'html'.")
    path = TEMPLATES_DIR / "examples" / fname
    if not path.exists():
        raise HTTPException(status_code=404, detail="Example template not found.")
    return Response(
        content=path.read_text(encoding="utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@router.get("/templates")
async def my_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    rows = await list_user_templates(db, current_user.id)
    return {
        "templates": [
            {"id": _custom_id(r), "template_id": str(r.id), "name": r.name,
             "format": r.format, "created_at": r.created_at}
            for r in rows
        ]
    }


@router.delete("/templates/{template_id}")
async def remove_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    try:
        await delete_user_template(db, template_id, current_user.id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Template not found.")
    return {"ok": True}


async def _load_application(db: AsyncSession, application_id: UUID, user: User) -> ApplicationModel:
    app_row = await db.scalar(
        select(ApplicationModel).where(ApplicationModel.id == application_id)
    )
    if app_row is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if app_row.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return app_row


async def _input_format(db: AsyncSession, app_row: ApplicationModel) -> str:
    master = await db.scalar(
        select(MasterCVModel).where(MasterCVModel.id == app_row.master_cv_id)
    )
    return master.file_type if master else "pdf"


@router.get("/applications/{application_id}/template-options")
async def template_options(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    from app.generation.render_dispatch import (
        builtin_choices,
        default_template_id,
        pdf_templates_allowed,
    )

    app_row = await _load_application(db, application_id, current_user)
    input_format = await _input_format(db, app_row)

    options = builtin_choices(input_format)
    if pdf_templates_allowed(input_format):
        for r in await list_user_templates(db, current_user.id):
            options.append({
                "id": _custom_id(r), "name": r.name,
                "description": f"Your uploaded {r.format.upper()} template",
                "output": "pdf", "kind": "custom",
            })

    selected = app_row.template_id or default_template_id(input_format)
    return {"selected": selected, "input_format": input_format, "options": options}


@router.patch("/applications/{application_id}/template")
async def set_application_template(
    application_id: UUID,
    payload: TemplateSelect,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    from app.generation.render_dispatch import CUSTOM_PREFIX, is_choice_allowed

    app_row = await _load_application(db, application_id, current_user)
    input_format = await _input_format(db, app_row)
    tid = payload.template_id

    if not is_choice_allowed(tid, input_format):
        raise HTTPException(status_code=400, detail="That template is not available for this CV.")
    if tid.startswith(CUSTOM_PREFIX):
        try:
            template_uuid = UUID(tid[len(CUSTOM_PREFIX):])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid template id.")
        if await get_user_template(db, template_uuid, current_user.id) is None:
            raise HTTPException(status_code=404, detail="Template not found.")

    app_row.template_id = tid
    await db.commit()
    return {"ok": True, "template_id": tid}
