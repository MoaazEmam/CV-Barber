"""Shared raw-text extraction — used only for the dedup hash.

Structure identification does its own span-level parse (see pdf/parse.py and
docx/parse.py); this returns a plain string purely so the orchestrator can
normalise + hash it and check the dedup cache before any LLM call.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Literal

from app.extraction.pdf import PdfExtractor
from app.extraction.docx_ import DocxExtractor

Fmt = Literal["pdf", "docx"]

_pdf = PdfExtractor()
_docx = DocxExtractor()


def extract_raw_text(file_path: str, fmt: Fmt) -> str:
    """Return the plain text of ``file_path`` for the given format."""
    if fmt == "pdf":
        return _pdf.extract_text(file_path)
    if fmt == "docx":
        return _docx.extract_text(file_path)
    raise ValueError(f"Unsupported format '{fmt}'. Supported: pdf, docx")


def extract_raw_text_from_bytes(file_bytes: bytes, fmt: Fmt) -> str:
    """Write bytes to a temp file, extract raw text, then clean up."""
    suffix = f".{fmt}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        return extract_raw_text(tmp_path, fmt)
    finally:
        os.unlink(tmp_path)


def fmt_from_filename(filename: str) -> Fmt:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".docx":
        return "docx"
    raise ValueError(f"Unsupported file type '{suffix}'. Supported: .pdf, .docx")
