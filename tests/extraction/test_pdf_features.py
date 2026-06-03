"""Tests for PDF link capture, scanned-PDF degradation, and golden no-regression."""

from pathlib import Path

import fitz

from app.extraction.pdf import PdfExtractor

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PDF = FIXTURES_DIR / "sample.pdf"


def _legacy_extract(path: str) -> str:
    """Replicates the pre-change extraction (plain get_text + clean)."""
    doc = fitz.open(path)
    pages = [page.get_text() for page in doc]
    doc.close()
    text = "\n".join(pages)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def test_links_are_appended(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    # Enough body text that the page is not mistaken for a scan.
    page.insert_textbox(fitz.Rect(72, 100, 520, 700), "Experienced engineer. " * 30, fontsize=11)
    page.insert_text((72, 80), "Find me on LinkedIn", fontsize=12)
    page.insert_link({
        "kind": fitz.LINK_URI,
        "from": fitz.Rect(72, 70, 200, 88),
        "uri": "https://linkedin.com/in/example",
    })
    out = tmp_path / "links.pdf"
    doc.save(str(out))
    doc.close()

    text = PdfExtractor().extract_text(str(out))
    assert "Links:" in text
    assert "https://linkedin.com/in/example" in text


def test_scanned_pdf_degrades_gracefully(tmp_path):
    # A page with no text layer looks scanned → OCR is attempted. Without
    # Tesseract it returns "" (logged, not raised); a blank page yields "" even
    # with Tesseract. Either way: no crash, empty result.
    doc = fitz.open()
    doc.new_page()  # blank, no text
    out = tmp_path / "blank.pdf"
    doc.save(str(out))
    doc.close()

    text = PdfExtractor().extract_text(str(out))
    assert text.strip() == ""


def test_golden_single_column_no_regression():
    # The known single-column sample must still take the default path: its body
    # (before any appended Links line) is byte-identical to the legacy extractor.
    new = PdfExtractor().extract_text(str(SAMPLE_PDF))
    body = new.split("\nLinks:")[0]
    assert body == _legacy_extract(str(SAMPLE_PDF))
