"""DOCX span parsing.

Emits one normalised :class:`~app.pipeline.spans.Span` per body paragraph. The
span ``id`` encodes the paragraph index (``"p{n}"``) so the renderer can locate
the original paragraph object to delete, move, or rewrite. Run-level styling is
summarised onto the paragraph span (bold if any run is bold, size/font/style
from the first run / paragraph style).
"""

from __future__ import annotations

import io

from docx import Document
from docx.shared import Pt

from app.pipeline.spans import Span


def _first_run_meta(paragraph):
    size = 0.0
    font = None
    bold = False
    italic = False
    for run in paragraph.runs:
        if run.bold:
            bold = True
        if run.italic:
            italic = True
        if font is None and run.font and run.font.name:
            font = run.font.name
        if not size and run.font and run.font.size:
            try:
                size = run.font.size / Pt(1)
            except (TypeError, ValueError):
                pass
    return size, font, bold, italic


def parse_spans(file_bytes: bytes) -> list[Span]:
    """Extract one Span per non-empty body paragraph from DOCX bytes."""
    doc = Document(io.BytesIO(file_bytes))
    spans: list[Span] = []
    for idx, paragraph in enumerate(doc.paragraphs):
        text = paragraph.text.strip()
        if not text:
            continue
        size, font, bold, italic = _first_run_meta(paragraph)
        style = paragraph.style.name if paragraph.style else None
        spans.append(
            Span(
                id=f"p{idx}",
                text=text,
                size=size,
                bold=bold,
                italic=italic,
                font=font,
                style=style,
            )
        )
    return spans
