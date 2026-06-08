"""Format-agnostic span metadata.

Both the PDF parser (pymupdf glyph spans) and the DOCX parser (python-docx runs)
normalise their output into a list of :class:`Span` before structure
identification, so the Tier 1 structure prompt never sees format-specific shapes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Span:
    """One contiguous run of text with the styling metadata used to infer role.

    ``id`` is a stable identifier the structure map references back to. For PDF
    it is a synthetic running index; for DOCX it encodes the paragraph (and run)
    index so the renderer can locate the original object: ``"p12"`` or ``"p12.r0"``.
    """

    id: str
    text: str
    # Font size in points (rounded). 0 when the format does not expose it.
    size: float = 0.0
    bold: bool = False
    italic: bool = False
    font: Optional[str] = None
    # Hex colour string (e.g. "#1a1a1a") or None when unknown.
    color: Optional[str] = None
    # Page (PDF) or section (DOCX) the span belongs to; 0 when not applicable.
    page: int = 0
    # Bounding box (x0, y0, x1, y1) for PDF; None for DOCX.
    bbox: Optional[tuple[float, float, float, float]] = None
    # Word paragraph style name (DOCX only), e.g. "Heading 1"; None for PDF.
    style: Optional[str] = None

    def to_prompt_dict(self) -> dict:
        """Compact dict fed to the structure LLM — drops null/zero noise."""
        d = {"id": self.id, "text": self.text}
        if self.size:
            d["size"] = round(self.size, 1)
        if self.bold:
            d["bold"] = True
        if self.italic:
            d["italic"] = True
        if self.font:
            d["font"] = self.font
        if self.style:
            d["style"] = self.style
        if self.page:
            d["page"] = self.page
        return d

    def as_dict(self) -> dict:
        return asdict(self)
