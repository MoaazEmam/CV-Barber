import fitz


class PdfExtractor:
    def extract_text(self, path: str) -> str:
        doc = fitz.open(path)

        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text())

        doc.close()

        return self._clean_text("\n".join(pages))

    def _clean_text(self, text: str) -> str:
        cleaned: list[str] = []

        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                cleaned.append(stripped)

        return "\n".join(cleaned)