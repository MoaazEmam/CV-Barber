"""render_dispatch gate logic + custom-template sandbox (no WeasyPrint/Tectonic).

The SSTI exploits raise inside the Jinja sandbox *before* any external renderer
runs, so these assert the security boundary without needing GTK/Tectonic.
"""
import pytest

from app.generation import render_dispatch as rd
from app.schemas.tailored_cv import TailoredCV


def _cv():
    return TailoredCV(full_name="X", job_title="Eng", company_name="Co")


def test_keep_original_is_docx_only():
    assert rd.is_choice_allowed("keep_original", "docx") is True
    assert rd.is_choice_allowed("keep_original", "pdf") is False


def test_pdf_templates_gated_for_docx(monkeypatch):
    monkeypatch.setattr(rd.settings, "allow_docx_to_pdf", False)
    assert rd.is_choice_allowed("builtin:classic", "pdf") is True
    assert rd.is_choice_allowed("builtin:classic", "docx") is False
    assert rd.is_choice_allowed("custom:abc", "docx") is False


def test_docx_to_pdf_flag_opens_gate(monkeypatch):
    monkeypatch.setattr(rd.settings, "allow_docx_to_pdf", True)
    assert rd.is_choice_allowed("builtin:classic", "docx") is True
    ids = [o["id"] for o in rd.builtin_choices("docx")]
    assert "keep_original" in ids and "builtin:classic" in ids


def test_default_template_id(monkeypatch):
    monkeypatch.setattr(rd.settings, "allow_docx_to_pdf", False)
    assert rd.default_template_id("pdf") == "builtin:classic"
    assert rd.default_template_id("docx") == "keep_original"


def test_builtin_choices_counts(monkeypatch):
    monkeypatch.setattr(rd.settings, "allow_docx_to_pdf", False)
    assert len(rd.builtin_choices("pdf")) == 5
    assert [o["id"] for o in rd.builtin_choices("docx")] == ["keep_original"]


@pytest.mark.parametrize("evil", [
    "{{ ''.__class__.__mro__[1].__subclasses__() }}",
    "{{ ().__class__.__bases__[0].__subclasses__() }}",
    "{{ cv.__init__.__globals__['os'] }}",
])
def test_custom_html_blocks_ssti(evil):
    with pytest.raises(rd.TemplateRenderError):
        rd._render_custom_html(evil, _cv())


@pytest.mark.parametrize("evil", [
    r"\VAR{ ''.__class__.__mro__[1].__subclasses__() }",
    r"\VAR{ cv.__class__.__base__.__subclasses__() }",
])
def test_custom_tex_blocks_ssti(evil):
    with pytest.raises(rd.TemplateRenderError):
        rd._render_custom_tex(evil, _cv())
