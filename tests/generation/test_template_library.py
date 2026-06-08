"""Built-in template library: Jinja render (no WeasyPrint) of every theme with
full and sparse data — proves macros work and empty sections are omitted."""
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas.tailored_cv import TailoredCV

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "app" / "generation" / "templates"
BUILTINS = ["classic.html", "modern.html", "compact.html", "professional.html", "minimal.html"]


@pytest.fixture
def env():
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _full():
    return TailoredCV(
        full_name="Rania Fares", email="r@x.com", phone="+201069398773", location="Cairo, Egypt",
        linkedin="linkedin.com/in/rania", github="github.com/rania",
        tailored_summary="Mechatronics engineer.",
        experience=[{"title": "Intern", "company": "GM Egypt", "location": "Cairo",
                     "bullets": ["Did X"], "date_range": {"start": "2025", "end": "2025"},
                     "relevance_score": 8, "relevance_reason": "x"}],
        projects=[{"name": "Palletizer", "description": "Systems design", "tech_stack": ["CAD"],
                   "bullets": ["Led team"], "date_range": {"start": None, "end": None},
                   "relevance_score": 9, "relevance_reason": "x"}],
        skills=[{"category": "Programming", "skills": ["C", "Python"]}],
        education=[{"institution": "University of Hertfordshire", "degree": "B.S.", "field": "Mechatronics",
                    "gpa": "4.5", "relevant_courses": ["Control Systems"],
                    "date_range": {"start": "2023", "end": "2027"}}],
        certifications=["FMEA Specialist"],
        additional_sections=[
            {"title": "Honors & Awards", "entries": [{"heading": "NASA Apps", "subheading": "First Place", "bullets": ["Won"]}]},
            {"title": "Languages", "entries": [{"detail": "Arabic (Native); English (Fluent)"}]},
        ],
        job_title="Engineer", company_name="Place",
    )


def _sparse():
    return TailoredCV(
        full_name="Jane Doe", email="j@x.com",
        experience=[{"title": "Dev", "company": "Acme", "bullets": ["Built stuff"],
                     "date_range": {"start": "2020", "end": "2022"}, "relevance_score": 5, "relevance_reason": "x"}],
        job_title="Engineer", company_name="Place",
    )


@pytest.mark.parametrize("fn", BUILTINS)
def test_builtin_renders_full(env, fn):
    html = env.get_template(fn).render(cv=_full())
    assert "Rania Fares" in html
    assert "Honors &amp; Awards" in html          # preserved extra section rendered
    assert "Arabic (Native)" in html              # languages detail rendered
    assert "FMEA Specialist" in html
    for heading in ("Summary", "Education", "Experience", "Projects", "Skills", "Certifications"):
        assert heading in html, f"{fn} missing heading {heading}"


@pytest.mark.parametrize("fn", BUILTINS)
def test_builtin_omits_empty_sections(env, fn):
    html = env.get_template(fn).render(cv=_sparse())
    for heading in ("Skills", "Education", "Projects", "Certifications", "Summary", "Honors"):
        assert heading not in html, f"{fn} leaked '{heading}' with no data"
    assert "Experience" in html and "Jane Doe" in html


def test_registry_has_at_least_five_builtins():
    from app.generation.template_registry import get_builtin, list_builtins

    builtins = list_builtins()
    assert len(builtins) >= 5
    for b in builtins:
        assert b.path.exists(), f"missing template file {b.filename}"
    assert get_builtin("classic") is not None
    assert get_builtin("does-not-exist") is None
