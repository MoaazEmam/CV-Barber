"""Real PDF render checks (WeasyPrint + Tectonic). Skipped where the native libs
aren't available (e.g. local Windows without GTK); runs in-container / CI."""
import shutil

import pytest

try:  # GTK/Pango (WeasyPrint) + PyMuPDF native libs
    import weasyprint  # noqa: F401
    import fitz
except Exception:  # noqa: BLE001
    pytest.skip("WeasyPrint/PyMuPDF native libs unavailable", allow_module_level=True)

from app.generation.render_dispatch import (
    _render_custom_html,
    render_output,
    sample_tailored_cv,
)
from app.generation.template_registry import list_builtins

# Headings may be CSS-uppercased, so the ATS proxy matches case-insensitively and
# also asserts real body content from every section actually rendered.
ATS_NEEDLES = [
    "sample candidate", "sample@example.com", "acme corp", "widget platform",
    "python", "state university", "aws solutions architect", "hackathon winner",
    "english (native)", "education", "experience", "skills", "projects",
    "certifications", "awards",
]


def _text(pdf_bytes: bytes) -> str:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return "\n".join(p.get_text() for p in doc).lower()


@pytest.mark.parametrize("tid", [b.id for b in list_builtins()])
def test_builtin_renders_ats_friendly_pdf(tid):
    doc = render_output(f"builtin:{tid}", sample_tailored_cv(), None, input_format="pdf")
    assert doc.content[:4] == b"%PDF" and doc.extension == "pdf"
    text = _text(doc.content)
    missing = [n for n in ATS_NEEDLES if n not in text]
    assert not missing, f"{tid} ATS extraction missing {missing}"


def test_custom_html_renders_pdf():
    html = "<html><body><h1>{{ cv.full_name }}</h1></body></html>"
    pdf = _render_custom_html(html, sample_tailored_cv())
    assert pdf[:4] == b"%PDF"
    assert "sample candidate" in _text(pdf)


@pytest.mark.skipif(shutil.which("tectonic") is None, reason="tectonic not installed")
def test_custom_tex_renders_pdf():
    from app.generation.render_dispatch import _render_custom_tex

    tex = r"\documentclass{article}\begin{document}\VAR{cv.full_name}\end{document}"
    pdf = _render_custom_tex(tex, sample_tailored_cv())
    assert pdf[:4] == b"%PDF"
