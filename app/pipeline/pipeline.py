"""Pipeline orchestration — the one-time Tier-1 parse for a unique CV.

``run_parse`` extracts the structured :class:`MasterCV` from the upload (and, for
DOCX, the in-place-edit artifact + section map used by "keep original"). It
dispatches on ``fmt`` ("pdf" | "docx"); the result is cached against the dedup
hash. Rendering is handled separately by ``app.generation.render_dispatch``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import structlog

from app.pipeline.schema_extract import SchemaExtractor
from app.pipeline.structure import StructureIdentifier
from app.schemas.master_cv import MasterCV

log = structlog.get_logger()

Fmt = Literal["pdf", "docx"]


@dataclass
class ParseResult:
    master_cv: MasterCV
    template_artifact: str | None
    section_map: dict


async def run_parse(file_bytes: bytes, fmt: Fmt, raw_text: str) -> ParseResult:
    """Run the Tier 1 parse pipeline for one CV. One-time per unique CV."""
    template_artifact: str | None = None
    section_map: dict = {}

    if fmt == "pdf":
        # PDF renders from a user-chosen template (built-in or custom) at render
        # time, so it needs no per-CV artifact or structure map — only the schema
        # content extracted below.
        pass
    elif fmt == "docx":
        from app.pipeline.docx.parse import parse_spans
        from app.pipeline.docx.template import build_artifact

        # DOCX "keep original" edits the document in place; structure ID maps
        # paragraphs -> entries so the renderer can locate/delete/reorder them.
        spans = parse_spans(file_bytes)
        section_map = await StructureIdentifier().identify(spans)
        template_artifact = build_artifact(section_map)
    else:
        raise ValueError(f"Unsupported format '{fmt}'.")

    master_cv = await SchemaExtractor().extract(raw_text, section_map)
    log.info(
        "pipeline_parse_completed",
        fmt=fmt,
        experience=len(master_cv.experience),
        projects=len(master_cv.projects),
    )
    return ParseResult(master_cv=master_cv, template_artifact=template_artifact, section_map=section_map)
