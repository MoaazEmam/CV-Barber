from app.generation.base_generator import BaseGenerator
from app.config import Settings, settings as default_settings


class GeneratorFactory:
    def __init__(self, settings: Settings = default_settings):
        self._settings = settings

    def create(self) -> BaseGenerator:
        fmt = self._settings.output_format.lower()

        if fmt == "docx":
            from app.generation.docx_generator import DocxGenerator
            return DocxGenerator()

        if fmt == "pdf":
            from app.generation.pdf_generator import PdfGenerator
            return PdfGenerator()

        raise ValueError(
            f"Unknown output format '{fmt}'. "
            "Valid options: 'docx', 'pdf'"
        )