from collections import defaultdict

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
            pages = list(doc)
            # De-overprint first: some CVs draw each glyph many times for a faux-bold
            # effect, so a hyperlinked word like "Certificate" extracts as 17 repeated
            # lines. Left in, that pollutes the parser input (and mis-splits sections).
            page_texts = [self._dedupe_overprint(self._page_text(page)) for page in pages]
            text = "\n".join(page_texts)

            if self._looks_scanned(text, doc.page_count):
                ocr_text = self._ocr(doc)
                if len(ocr_text.strip()) > len(text.strip()):
                    # A scanned page has no hyperlink layer, so there is nothing to
                    # inline or append — return the OCR text as-is.
                    return self._clean_text(ocr_text)

            # Inline each hyperlink next to its anchor text so the parser can keep
            # it with the right item (e.g. a certificate's verification link stays
            # on that certificate line instead of floating to the top).
            text = "\n".join(
                self._inline_links(page, pt) for page, pt in zip(pages, page_texts)
            )
            links = self._collect_links(doc)
        finally:
            doc.close()

        # Also append the flat list of targets — a safety net for links whose
        # anchor text couldn't be located (and for filling linkedin/github/website
        # when the visible text was only a label like "LinkedIn").
        if links:
            text = f"{text}\nLinks: {' '.join(links)}"

        return self._clean_text(text)

    @staticmethod
    def _collapse_repeats(s: str) -> str:
        """Collapse consecutive duplicate tokens ("Certificate Certificate …" → one)."""
        out: list[str] = []
        for tok in s.split():
            if not out or out[-1] != tok:
                out.append(tok)
        return " ".join(out)

    def _dedupe_overprint(self, text: str) -> str:
        """Strip faux-bold overprint: a word redrawn N times extracts as N identical
        lines (or a single-word remnant adjacent to the real line). Keep one copy."""
        out: list[str] = []
        for raw in text.splitlines():
            s = raw.strip()
            if not s:
                continue
            if out:
                prev = out[-1]
                if s == prev:
                    continue
                # current line is a single-word trailing remnant of the previous line
                if " " not in s and len(prev) > len(s) and prev.endswith(s) \
                        and not prev[-len(s) - 1].isalnum():
                    continue
                # previous line was a single-word leading remnant of this line
                if " " not in prev and len(s) > len(prev) and s.startswith(prev) \
                        and not s[len(prev)].isalnum():
                    out.pop()
            out.append(s)
        return "\n".join(out)

    def _inline_links(self, page, text: str) -> str:
        """Insert ``(uri)`` immediately after each link's anchor text within *text*.

        Links are matched to anchor occurrences in reading order, so repeated
        anchors (e.g. three "Certificate" links) attach to the correct line."""
        annotations = []
        for link in page.get_links():
            uri = link.get("uri")
            rect = link.get("from")
            if not uri or rect is None:
                continue
            anchor = self._collapse_repeats(page.get_textbox(rect))
            annotations.append((round(rect.y0), round(rect.x0), anchor, uri))
        if not annotations:
            return text

        annotations.sort(key=lambda a: (a[0], a[1]))
        used: dict[str, int] = defaultdict(int)
        for _, _, anchor, uri in annotations:
            if not anchor or uri in text:
                continue
            idx = self._nth_index(text, anchor, used[anchor])
            used[anchor] += 1
            if idx == -1:
                continue  # anchor not found in flowed text — fall back to Links: line
            insert_at = idx + len(anchor)
            text = f"{text[:insert_at]} ({uri}){text[insert_at:]}"
        return text

    @staticmethod
    def _nth_index(text: str, sub: str, n: int) -> int:
        """Index of the (n+1)-th occurrence of *sub* in *text*, or -1."""
        start = 0
        idx = -1
        for _ in range(n + 1):
            idx = text.find(sub, start)
            if idx == -1:
                return -1
            start = idx + len(sub)
        return idx

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
