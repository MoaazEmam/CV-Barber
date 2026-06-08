"""PDF span parsing.

Reads glyph-level spans with styling metadata via PyMuPDF's ``get_text("dict")``
and normalises them into the shared :class:`~app.pipeline.spans.Span` format for
structure identification. Also renders pages to PNG for the vision template step.
"""

from __future__ import annotations

import fitz  # PyMuPDF

from app.pipeline.spans import Span

# PyMuPDF span flag bits.
_FLAG_ITALIC = 1 << 1  # 2
_FLAG_BOLD = 1 << 4  # 16


def _color_to_hex(color: int) -> str | None:
    try:
        return "#%06x" % (int(color) & 0xFFFFFF)
    except (TypeError, ValueError):
        return None


def parse_spans(file_bytes: bytes) -> list[Span]:
    """Extract normalised spans from PDF bytes, in reading order."""
    spans: list[Span] = []
    counter = 0
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page_index, page in enumerate(doc):
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                if block.get("type") != 0:  # 0 = text block
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = (span.get("text") or "").strip()
                        if not text:
                            continue
                        flags = span.get("flags", 0)
                        font = span.get("font") or ""
                        spans.append(
                            Span(
                                id=f"s{counter}",
                                text=text,
                                size=float(span.get("size", 0.0)),
                                bold=bool(flags & _FLAG_BOLD) or "bold" in font.lower(),
                                italic=bool(flags & _FLAG_ITALIC)
                                or "italic" in font.lower(),
                                font=font or None,
                                color=_color_to_hex(span.get("color", 0)),
                                page=page_index,
                                bbox=tuple(span.get("bbox")) if span.get("bbox") else None,
                            )
                        )
                        counter += 1
    return spans


def render_pages_png(file_bytes: bytes, dpi: int = 130, max_pages: int = 3) -> list[bytes]:
    """Render the first ``max_pages`` pages to PNG bytes for the vision LLM.

    Default 130 DPI keeps each page's base64 payload comfortably under Groq's
    4MB/image limit while staying legible for the model.
    """
    pngs: list[bytes] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc[:max_pages]:
            pix = page.get_pixmap(matrix=matrix)
            pngs.append(pix.tobytes("png"))
    return pngs
