"""Custom template upload + per-application template selection.

- POST   /api/templates                              upload a .html/.tex template (sandbox test-render, then store)
- GET    /api/templates                              list the user's uploaded templates
- DELETE /api/templates/{template_id}                delete one
- GET    /api/applications/{id}/template-options     choices allowed for that application + the selected one
- PATCH  /api/applications/{id}/template             set the chosen template

User templates are rendered ONLY in a sandbox (see render_dispatch): Jinja
SandboxedEnvironment, WeasyPrint with a blocked url_fetcher, Tectonic --untrusted.
"""
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
    get_user_template_by_hash,
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

_AUTO_CONVERTED_NOTE = (
    "We noticed your file had no placeholders, so we automatically converted it "
    "into a tailoring template. Preview it before downloading to confirm the "
    "layout looks right."
)
_NO_PLACEHOLDER_WARNING = (
    "We couldn't add placeholders to this template automatically, so it will "
    "render the same content for every job (e.g. \\VAR{ cv.full_name } for .tex "
    "or {{ cv.full_name }} for .html). Download the example template to see the "
    "expected format."
)


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

    # Dedup on the *original* upload (pre-conversion): a re-upload of the same file
    # returns the stored template immediately — no new row, no LLM conversion call.
    from app.pipeline.dedup import text_hash

    source_hash = text_hash(source)
    duplicate = await get_user_template_by_hash(db, current_user.id, source_hash)
    if duplicate is not None:
        log.info("custom_template_duplicate", template_id=str(duplicate.id), fmt=fmt)
        return {
            "id": _custom_id(duplicate), "template_id": str(duplicate.id),
            "name": duplicate.name, "format": duplicate.format,
            "warning": None, "converted": False, "duplicate": True,
            "note": "You already uploaded this template — selecting the existing one.",
        }

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
    from app.llm.exceptions import LLMAllKeysExhaustedError, LLMRateLimitError, LLMValidationError
    from app.llm.template_converter import (
        MAX_CONVERT_CHARS,
        PLACEHOLDER_RE,
        TemplateConverter,
    )

    renderer = _render_custom_tex if fmt == "tex" else _render_custom_html

    async def _test_render(src: str) -> None:
        """Raises TemplateRenderError if the source doesn't compile in the sandbox."""
        await run_in_threadpool(renderer, src, sample_tailored_cv())

    def _reject() -> None:
        raise HTTPException(
            status_code=422,
            detail="That template failed to render. Check the template and try again.",
        )

    store_source = source
    converted = False
    warning: str | None = None
    note: str | None = None

    if PLACEHOLDER_RE.search(source):
        # Already a real template — render as-is to validate it compiles.
        try:
            await _test_render(source)
        except TemplateRenderError as e:
            log.warning("custom_template_rejected", error=str(e), fmt=fmt)
            _reject()
    else:
        # A filled-in document with no placeholders would render the same PDF for
        # every job. Try to templatize it (LLM) so it can actually be tailored;
        # fall back to storing the original on any failure (never lose the upload).
        templatized: str | None = None
        if len(source) <= MAX_CONVERT_CHARS:
            try:
                # `validate=_test_render` drives a compile-repair loop inside the
                # converter: a non-compiling result is fed back to the LLM to fix.
                templatized = await TemplateConverter().convert(
                    source, fmt, validate=_test_render, max_repairs=2
                )
            except (LLMRateLimitError, LLMAllKeysExhaustedError) as e:
                log.info("template_convert_unavailable", error=str(e), fmt=fmt)
            except (LLMValidationError, TemplateRenderError) as e:
                log.info("template_convert_failed", error=str(e), fmt=fmt)
        else:
            log.info("template_convert_skipped_too_large", chars=len(source), fmt=fmt)

        if templatized is not None:
            store_source = templatized
            converted = True
            note = _AUTO_CONVERTED_NOTE
        else:
            # Couldn't convert — store the original, but only after confirming it
            # compiles so we never save something that won't render.
            try:
                await _test_render(source)
            except TemplateRenderError as e:
                log.warning("custom_template_rejected", error=str(e), fmt=fmt)
                _reject()
            warning = _NO_PLACEHOLDER_WARNING

    name = file.filename or f"template.{fmt}"
    template_uuid = await create_user_template(
        db, current_user.id, name, fmt, store_source, source_hash=source_hash
    )
    log.info("custom_template_saved", template_id=str(template_uuid), fmt=fmt, converted=converted)

    return {
        "id": f"custom:{template_uuid}", "template_id": str(template_uuid),
        "name": name, "format": fmt, "warning": warning, "note": note, "converted": converted,
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
