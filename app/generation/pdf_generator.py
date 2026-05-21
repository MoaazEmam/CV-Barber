from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
from pathlib import Path

from app.generation.base_generator import BaseGenerator
from app.generation.section_filter import apply_section_config
from app.schemas.tailored_cv import TailoredCV


TEMPLATES_DIR = Path(__file__).parent / "templates"


class PdfGenerator(BaseGenerator):
    def __init__(self):
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def generate(self, cv: TailoredCV, section_config: dict | None = None) -> bytes:
        cv = apply_section_config(cv, section_config)
        template = self._env.get_template("cv.html")
        html_string = template.render(cv=cv)
        return HTML(string=html_string).write_pdf()

    def content_type(self) -> str:
        return "application/pdf"

    def file_extension(self) -> str:
        return "pdf"