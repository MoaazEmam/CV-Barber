"""ODT extraction: text in document order, table cells, and a Links: line."""

import io
import os
import tempfile
import zipfile

import pytest

from app.extraction.extractor import SUPPORTED_EXTENSIONS, TextExtractor
from app.extraction.odt_ import OdtExtractor
from app.generation.render_dispatch import (
    KEEP_ORIGINAL,
    builtin_choices,
    default_template_id,
    is_choice_allowed,
    pdf_templates_allowed,
)
from app.pipeline.extract import fmt_from_filename

CONTENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
    xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <office:body><office:text>
    <text:h>Jane Doe</text:h>
    <text:p>Software <text:span>Engineer</text:span></text:p>
    <text:p>Find me on <text:a xlink:href="https://github.com/jane">GitHub</text:a></text:p>
    <text:p><text:a xlink:href="mailto:jane@example.com">jane@example.com</text:a></text:p>
    <table:table><table:table-row>
      <table:table-cell><text:p>Python</text:p></table:table-cell>
      <table:table-cell><text:p>Docker</text:p></table:table-cell>
    </table:table-row></table:table>
    <text:p></text:p>
  </office:text></office:body>
</office:document-content>"""


def _make_odt(content_xml: str = CONTENT_XML) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        zf.writestr("content.xml", content_xml)
    return buf.getvalue()


@pytest.fixture
def odt_path(tmp_path):
    p = tmp_path / "cv.odt"
    p.write_bytes(_make_odt())
    return str(p)


def test_extracts_paragraphs_in_order(odt_path):
    text = OdtExtractor().extract_text(odt_path)
    lines = text.splitlines()
    assert lines[0] == "Jane Doe"
    assert lines[1] == "Software Engineer"
    assert "Python" in lines
    assert "Docker" in lines
    assert lines.index("Jane Doe") < lines.index("Python")


def test_collects_links_excluding_mailto(odt_path):
    text = OdtExtractor().extract_text(odt_path)
    assert text.splitlines()[-1] == "Links: https://github.com/jane"
    assert "mailto:" not in text


def test_text_extractor_dispatches_odt():
    assert ".odt" in SUPPORTED_EXTENSIONS
    text = TextExtractor().extract_cv_text_from_bytes(_make_odt(), "cv.odt")
    assert "Jane Doe" in text


def test_fmt_from_filename_odt():
    assert fmt_from_filename("cv.odt") == "odt"


def test_odt_render_gates():
    # ODT behaves like PDF: PDF templates always allowed, never keep_original.
    assert pdf_templates_allowed("odt") is True
    assert is_choice_allowed(KEEP_ORIGINAL, "odt") is False
    assert default_template_id("odt").startswith("builtin:")
    ids = [c["id"] for c in builtin_choices("odt")]
    assert KEEP_ORIGINAL not in ids
    assert any(i.startswith("builtin:") for i in ids)
