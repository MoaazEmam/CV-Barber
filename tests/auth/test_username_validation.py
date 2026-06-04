"""Unit tests for the username policy enforced at registration.

Tests the pure ``validate_username`` helper directly — no DB or HTTP needed
(conftest provides no app/client fixture). Policy: letters + numbers only,
3–30 characters.
"""

import pytest
from fastapi import HTTPException

from app.auth.validation import validate_username


@pytest.mark.parametrize("name", ["john_doe", "jane-smith", "joe!", "a b", "john.doe"])
def test_rejects_non_alphanumeric(name):
    with pytest.raises(HTTPException) as exc_info:
        validate_username(name)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Username can only contain letters and numbers."


@pytest.mark.parametrize("name", ["", "a", "ab"])
def test_rejects_too_short(name):
    with pytest.raises(HTTPException) as exc_info:
        validate_username(name)
    assert exc_info.value.status_code == 400
    assert "at least 3" in exc_info.value.detail


def test_rejects_too_long():
    with pytest.raises(HTTPException) as exc_info:
        validate_username("a" * 31)
    assert exc_info.value.status_code == 400
    assert "at most 30" in exc_info.value.detail


@pytest.mark.parametrize("name", ["abc", "johndoe", "jane2026", "ABC123", "a" * 30])
def test_accepts_valid(name):
    # Should not raise.
    validate_username(name)
