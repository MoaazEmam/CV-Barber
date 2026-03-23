# tests/generation/test_pdf_generator.py
import pytest
from app.generation.pdf_generator import PdfGenerator
from tests.generation.test_docx_generator import sample_tailored_cv  # reuse fixture


@pytest.fixture
def generator() -> PdfGenerator:
    return PdfGenerator()


class TestPdfGenerator:
    def test_returns_bytes(self, generator, sample_tailored_cv):
        result = generator.generate(sample_tailored_cv)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_output_starts_with_pdf_header(self, generator, sample_tailored_cv):
        result = generator.generate(sample_tailored_cv)
        assert result[:4] == b"%PDF"

    def test_content_type(self, generator):
        assert generator.content_type() == "application/pdf"

    def test_file_extension(self, generator):
        assert generator.file_extension() == "pdf"

    def test_filename_format(self, generator, sample_tailored_cv):
        name = generator.filename(sample_tailored_cv)
        assert name == "moaaz_emam_ahmed_acme_corp.pdf"