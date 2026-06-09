"""Shared helper to render an application's tailored CV with its chosen template.

Used by both the preview and download routes so they stay in sync. The actual
render (WeasyPrint / Tectonic / python-docx) is synchronous and blocking, so it
runs in a threadpool.
"""
from uuid import UUID

import structlog
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApplicationModel, MasterCVModel
from app.schemas.tailored_cv import TailoredCV

log = structlog.get_logger()


async def resolve_template(db: AsyncSession, application: ApplicationModel):
    """Return ``(master_row | None, input_format, resolved_template_id)``."""
    from app.generation.render_dispatch import default_template_id

    master = await db.scalar(
        select(MasterCVModel).where(MasterCVModel.id == application.master_cv_id)
    )
    input_format = master.file_type if master else "pdf"
    template_id = application.template_id or default_template_id(input_format)
    return master, input_format, template_id


async def render_application(db: AsyncSession, application: ApplicationModel):
    """Render the application's tailored CV with its chosen template -> RenderedDoc."""
    from app.api.dependencies import get_user_template
    from app.generation.render_dispatch import (
        CUSTOM_PREFIX,
        default_template_id,
        render_output,
    )

    master, input_format, template_id = await resolve_template(db, application)
    tailored_cv = TailoredCV.model_validate(application.tailored_cv_data)

    custom_source = custom_format = None
    if template_id.startswith(CUSTOM_PREFIX):
        try:
            tpl = await get_user_template(
                db, UUID(template_id[len(CUSTOM_PREFIX):]), application.user_id
            )
        except ValueError:
            tpl = None
        if tpl is None:
            # The custom template was deleted — fall back to the format default.
            template_id = default_template_id(input_format)
        else:
            custom_source, custom_format = tpl.source, tpl.format

    return await run_in_threadpool(
        render_output,
        template_id,
        tailored_cv,
        application.section_config,
        input_format=input_format,
        raw_file=master.raw_file if master else None,
        docx_artifact=master.template_artifact if master else None,
        custom_source=custom_source,
        custom_format=custom_format,
    )
