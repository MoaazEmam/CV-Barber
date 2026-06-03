"""Unit tests for the parse-quality warning logic (app.api.routes.parse)."""

from app.api.routes.parse import MIN_CV_TEXT_CHARS, _parse_warnings


def test_warns_when_no_experience_or_projects():
    warnings = _parse_warnings("Jane Doe", "jane@example.com", 0, 0, 3)
    assert any("experience or projects" in w for w in warnings)


def test_warns_when_missing_name_or_email():
    assert any("name or email" in w for w in _parse_warnings("", "jane@example.com", 1, 1, 1))
    assert any("name or email" in w for w in _parse_warnings("Jane", None, 1, 1, 1))


def test_warns_when_no_skills():
    warnings = _parse_warnings("Jane Doe", "jane@example.com", 2, 1, 0)
    assert any("skills" in w.lower() for w in warnings)


def test_clean_parse_has_no_warnings():
    assert _parse_warnings("Jane Doe", "jane@example.com", 2, 3, 5) == []


def test_min_text_threshold_is_positive():
    assert MIN_CV_TEXT_CHARS > 0
