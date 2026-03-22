import tempfile
import os
from pathlib import Path
from app.extraction.pdf import PdfExtractor
from app.extraction.docx_ import DocxExtractor

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

class TextExtractor:
    def __init__(self):
        self.pdf_extractor=PdfExtractor()
        self.docx_extractor=DocxExtractor()
    def extract_cv_text(self,path:str):
        """
        Extract raw text from a CV file at the given path.
        Supports PDF and DOCX.
        """
        suffix = Path(path).suffix.lower()

        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{suffix}'. "
                f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        if suffix == ".pdf":
            return self.pdf_extractor.extract_text(path)
        elif suffix == ".docx":
            return self.docx_extractor.extract_text(path)
        else:
            return None

    def extract_cv_text_from_bytes(self,file_bytes: bytes, filename: str) -> str:
        """
        Extract raw text from file bytes — used by the Streamlit UI
        which receives uploaded files as bytes, not file paths.
        Writes to a temp file, extracts, then cleans up.
        """
        suffix = Path(filename).suffix.lower()

        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{suffix}'. "
                f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            return self.extract_cv_text(tmp_path)
        finally:
            os.unlink(tmp_path)