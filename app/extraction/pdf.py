import fitz
import structlog

from app.config import settings
from app.extraction._columns import read_in_columns

log = structlog.get_logger()

# Below this many characters of extracted text per page, a PDF almost certainly
# has no real text layer (a scan/photo) and is worth an OCR attempt.
_OCR_CHARS_PER_PAGE = 100


class PdfExtractor:
    def extract_text(self, path: str) -> str:
        doc = fitz.open(path)
        try:
            text = "\n".join(self._page_text(page) for page in doc)

            if self._looks_scanned(text, doc.page_count):
                ocr_text = self._ocr(doc)
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text

            links = self._collect_links(doc)
        finally:
            doc.close()

        # Append real hyperlink targets — visible text is often just "LinkedIn"
        # while the URL lives in the link annotation, so the parser would miss it.
        if links:
            text = f"{text}\nLinks: {' '.join(links)}"

        return self._clean_text(text)

    def _page_text(self, page) -> str:
        """Column-aware text for one page; default order for single-column pages."""
        columnar = read_in_columns(page)
        return columnar if columnar is not None else page.get_text()

    def _looks_scanned(self, text: str, page_count: int) -> bool:
        if not settings.ocr_enabled or page_count <= 0:
            return False
        return len(text.strip()) < _OCR_CHARS_PER_PAGE * page_count

    def _ocr(self, doc) -> str:
        """OCR every page via PyMuPDF's Tesseract integration.

        Returns "" (and logs) when Tesseract is unavailable — the caller then
        keeps the original near-empty text, which drives a parse warning rather
        than crashing.
        """
        tessdata = settings.tessdata_prefix or None
        try:
            pages = []
            for page in doc:
                tp = page.get_textpage_ocr(
                    flags=0, dpi=settings.ocr_dpi, full=True, tessdata=tessdata
                )
                pages.append(page.get_text(textpage=tp))
            log.info("pdf_ocr_completed", pages=doc.page_count)
            return "\n".join(pages)
        except Exception as e:  # tesseract missing / OCR failure — degrade gracefully
            log.warning("pdf_ocr_unavailable", error=str(e))
            return ""

    def _collect_links(self, doc) -> list[str]:
        seen: list[str] = []
        for page in doc:
            for link in page.get_links():
                uri = link.get("uri")
                if uri and uri not in seen:
                    seen.append(uri)
        return seen

    def _clean_text(self, text: str) -> str:
        cleaned = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(cleaned)
