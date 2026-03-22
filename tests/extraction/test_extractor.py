import pytest
import os
import tempfile
from pathlib import Path

from app.extraction import TextExtractor

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PDF = FIXTURES_DIR / "sample.pdf"
SAMPLE_DOCX = FIXTURES_DIR / "sample.docx"


@pytest.fixture
def extractor() -> TextExtractor:
    return TextExtractor()


def assert_basic_cv_content(text: str) -> None:
    assert len(text) > 100
    assert "\n" in text


class TestExtractCvText:
    def test_extracts_pdf(self, extractor):
        text = extractor.extract_cv_text(str(SAMPLE_PDF))
        assert_basic_cv_content(text)

    def test_extracts_docx(self, extractor):
        text = extractor.extract_cv_text(str(SAMPLE_DOCX))
        assert_basic_cv_content(text)

    def test_unsupported_extension_raises(self, extractor, tmp_path):
        fake_file = tmp_path / "cv.txt"
        fake_file.write_text("some content")
        with pytest.raises(ValueError, match="Unsupported file type"):
            extractor.extract_cv_text(str(fake_file))

    def test_output_has_no_leading_trailing_whitespace_per_line(self, extractor):
        text = extractor.extract_cv_text(str(SAMPLE_PDF))
        for line in text.splitlines():
            assert line == line.strip()

    def test_output_has_no_blank_lines(self, extractor):
        text = extractor.extract_cv_text(str(SAMPLE_PDF))
        for line in text.splitlines():
            assert line.strip() != ""

    def test_returns_string(self, extractor):
        result = extractor.extract_cv_text(str(SAMPLE_PDF))
        assert isinstance(result, str)


class TestExtractCvTextFromBytes:
    def test_pdf_bytes_matches_path_extraction(self, extractor):
        path_result = extractor.extract_cv_text(str(SAMPLE_PDF))
        with open(SAMPLE_PDF, "rb") as f:
            bytes_result = extractor.extract_cv_text_from_bytes(f.read(), "sample.pdf")
        assert path_result == bytes_result

    def test_docx_bytes_matches_path_extraction(self, extractor):
        path_result = extractor.extract_cv_text(str(SAMPLE_DOCX))
        with open(SAMPLE_DOCX, "rb") as f:
            bytes_result = extractor.extract_cv_text_from_bytes(f.read(), "sample.docx")
        assert path_result == bytes_result

    def test_temp_file_is_cleaned_up(self, extractor, tmp_path):
        before = set(os.listdir(tempfile.gettempdir()))
        with open(SAMPLE_PDF, "rb") as f:
            extractor.extract_cv_text_from_bytes(f.read(), "sample.pdf")
        after = set(os.listdir(tempfile.gettempdir()))
        assert before == after

    def test_unsupported_extension_raises(self, extractor):
        with pytest.raises(ValueError, match="Unsupported file type"):
            extractor.extract_cv_text_from_bytes(b"some content", "cv.txt")


class TestSupportedExtensions:
    def test_pdf_is_supported(self):
        from app.extraction.extractor import SUPPORTED_EXTENSIONS
        assert ".pdf" in SUPPORTED_EXTENSIONS

    def test_docx_is_supported(self):
        from app.extraction.extractor import SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS