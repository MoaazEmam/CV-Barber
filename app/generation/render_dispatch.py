"""Unified render dispatch — pick the right engine for a template choice.

A ``template_id`` maps to an output:
  - ``keep_original``  -> DOCX in-place edit of the original upload (DOCX out)
  - ``builtin:<id>``   -> WeasyPrint render of a built-in HTML theme (PDF out)
  - ``custom:<uuid>``  -> sandboxed render of a user-uploaded .html/.tex (PDF out)

This module is pure (no DB/HTTP): the caller loads the original file bytes / DOCX
artifact and any custom-template source, and passes them in. Built-in/trusted HTML
uses the plain Jinja env; user templates use a Jinja sandbox + WeasyPrint with a
blocked ``url_fetcher`` (HTML) or Tectonic ``--untrusted`` (LaTeX).

The input->output coupling lives only in the gate helpers here (``is_choice_allowed``,
``builtin_choices``, ``default_template_id``) keyed on ``settings.allow_docx_to_pdf`` —
flip that flag to enable DOCX->PDF with no other change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from app.config import settings
from app.generation.section_filter import apply_section_config
from app.generation.template_registry import (
    DEFAULT_BUILTIN_ID,
    get_builtin,
    list_builtins,
)
from app.schemas.tailored_cv import TailoredCV

log = structlog.get_logger()

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

KEEP_ORIGINAL = "keep_original"
BUILTIN_PREFIX = "builtin:"
CUSTOM_PREFIX = "custom:"


@dataclass
class RenderedDoc:
    content: bytes
    content_type: str
    extension: str


class TemplateRenderError(RuntimeError):
    """Raised when a chosen template fails to render."""


# --- gate: which choices are allowed for an input format --------------------

def pdf_templates_allowed(input_format: str) -> bool:
    """PDF inputs may always use PDF templates; DOCX inputs only if the gate is on."""
    return input_format == "pdf" or settings.allow_docx_to_pdf


def is_choice_allowed(template_id: str, input_format: str) -> bool:
    if template_id == KEEP_ORIGINAL:
        return input_format == "docx"
    return pdf_templates_allowed(input_format)


def default_template_id(input_format: str) -> str:
    # DOCX defaults to keep-original (highest fidelity); the HTML/.tex templates are
    # still offered as options when allow_docx_to_pdf is on.
    if input_format == "docx":
        return KEEP_ORIGINAL
    return f"{BUILTIN_PREFIX}{DEFAULT_BUILTIN_ID}"


def builtin_choices(input_format: str) -> list[dict]:
    """Built-in choices offered for an input format (keep_original + HTML themes)."""
    choices: list[dict] = []
    if input_format == "docx":
        choices.append({
            "id": KEEP_ORIGINAL,
            "name": "Keep original (DOCX)",
            "description": "Edit your uploaded document in place — identical formatting.",
            "output": "docx",
            "kind": "builtin",
        })
    if pdf_templates_allowed(input_format):
        for t in list_builtins():
            choices.append({
                "id": f"{BUILTIN_PREFIX}{t.id}",
                "name": t.name,
                "description": t.description,
                "output": "pdf",
                "kind": "builtin",
            })
    return choices


# --- rendering --------------------------------------------------------------

def _blocked_url_fetcher(url: str):
    # Only allow inline data: URIs; block file:// and http(s):// to prevent local
    # file disclosure / SSRF from (user-uploaded) HTML templates.
    if url.startswith("data:"):
        from weasyprint.urls import default_url_fetcher
        return default_url_fetcher(url)
    raise ValueError(f"Blocked external resource in template: {url[:60]}")


def _weasyprint_pdf(html_string: str) -> bytes:
    from weasyprint import HTML
    return HTML(string=html_string, url_fetcher=_blocked_url_fetcher).write_pdf()


def _render_builtin(builtin, cv: TailoredCV) -> bytes:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from app.generation.template_registry import TEMPLATES_DIR

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template(builtin.filename).render(cv=cv)
    return _weasyprint_pdf(html)


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _render_custom_html(source: str, cv: TailoredCV) -> bytes:
    from jinja2 import select_autoescape
    from jinja2.sandbox import SandboxedEnvironment

    # Drop HTML comments before Jinja parses the template: a comment documenting
    # the contract (e.g. "{{ cv.full_name }}") would otherwise be parsed as a real
    # expression and crash. Comments never affect the rendered PDF.
    source = _HTML_COMMENT_RE.sub("", source)
    env = SandboxedEnvironment(
        autoescape=select_autoescape(["html", "xml"], default_for_string=True)
    )
    try:
        html = env.from_string(source).render(cv=cv)
    except Exception as e:  # SSTI / template errors
        raise TemplateRenderError(f"Custom HTML template failed to render: {e}") from e
    return _weasyprint_pdf(html)


def _render_custom_tex(source: str, cv: TailoredCV) -> bytes:
    from app.pipeline.pdf.render import TectonicError
    from app.pipeline.pdf.render import render as render_tex

    try:
        return render_tex(source, cv, untrusted=True)
    except TectonicError as e:
        raise TemplateRenderError(str(e)) from e
    except Exception as e:
        raise TemplateRenderError(f"Custom LaTeX template failed to render: {e}") from e


def render_output(
    template_id: str,
    tailored_cv: TailoredCV,
    section_config: dict | None = None,
    *,
    input_format: str,
    raw_file: bytes | None = None,
    docx_artifact: str | None = None,
    custom_source: str | None = None,
    custom_format: str | None = None,
) -> RenderedDoc:
    """Render ``tailored_cv`` with the chosen template and return bytes + metadata."""
    filtered = apply_section_config(tailored_cv, section_config)

    # Keep original: edit the uploaded DOCX in place (true format fidelity).
    if template_id == KEEP_ORIGINAL:
        if raw_file is None or not docx_artifact:
            raise TemplateRenderError(
                "keep_original requires the original DOCX file and its artifact."
            )
        from app.pipeline.docx.render import render as render_docx

        content = render_docx(raw_file, docx_artifact, filtered)
        return RenderedDoc(content, DOCX_CONTENT_TYPE, "docx")

    # Custom user-uploaded template (sandboxed) -> PDF.
    if template_id.startswith(CUSTOM_PREFIX):
        if not custom_source or custom_format not in ("html", "tex"):
            raise TemplateRenderError("Custom template source/format missing.")
        content = (
            _render_custom_tex(custom_source, filtered)
            if custom_format == "tex"
            else _render_custom_html(custom_source, filtered)
        )
        return RenderedDoc(content, PDF_CONTENT_TYPE, "pdf")

    # Built-in HTML theme -> PDF. Accepts "builtin:<id>" or a bare "<id>".
    builtin_id = (
        template_id[len(BUILTIN_PREFIX):]
        if template_id.startswith(BUILTIN_PREFIX)
        else template_id
    )
    builtin = get_builtin(builtin_id) or get_builtin(DEFAULT_BUILTIN_ID)
    content = _render_builtin(builtin, filtered)
    return RenderedDoc(content, PDF_CONTENT_TYPE, "pdf")


def output_filename(tailored_cv: TailoredCV, extension: str) -> str:
    name = (tailored_cv.full_name or "cv").lower().replace(" ", "_")
    company = (tailored_cv.company_name or "company").lower().replace(" ", "_")
    return f"{name}_{company}.{extension}"


def sample_tailored_cv() -> TailoredCV:
    """A representative CV used to test-render a custom template on upload — every
    section populated so loops/fields in the template are actually exercised."""
    return TailoredCV(
        full_name="Sample Candidate", email="sample@example.com", phone="+1 555 0100",
        location="Remote", linkedin="linkedin.com/in/sample", github="github.com/sample",
        tailored_summary="Experienced engineer with a track record of shipping reliable software.",
        experience=[{
            "title": "Senior Engineer", "company": "Acme Corp", "location": "Remote",
            "bullets": ["Led a team of 5", "Cut latency by 40%"],
            "date_range": {"start": "2021", "end": "Present"},
            "relevance_score": 9, "relevance_reason": "core",
        }],
        projects=[{
            "name": "Widget Platform", "description": "Internal tooling",
            "tech_stack": ["Python", "FastAPI"], "bullets": ["Built X", "Shipped Y"],
            "date_range": {"start": "2020", "end": "2021"},
            "relevance_score": 8, "relevance_reason": "core",
        }],
        skills=[{"category": "Languages", "skills": ["Python", "TypeScript", "Go"]}],
        education=[{
            "institution": "State University", "degree": "B.Sc.", "field": "Computer Science",
            "gpa": "3.9", "relevant_courses": ["Algorithms", "Databases"],
            "date_range": {"start": "2016", "end": "2020"},
        }],
        certifications=["AWS Solutions Architect"],
        additional_sections=[
            {"title": "Awards", "entries": [{"heading": "Hackathon Winner", "subheading": "2022", "bullets": ["1st of 50"]}]},
            {"title": "Languages", "entries": [{"detail": "English (Native); Spanish (Fluent)"}]},
        ],
        job_title="Software Engineer", company_name="Example Inc",
    )
