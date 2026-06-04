"""Key rotation: exhaustion must surface as proper LLM errors, never AttributeError.

Regression for the `KeyState.daily_exhausted` typo that turned all-keys-exhausted
into an AttributeError — which (a) bypassed the Gemini fallback in FallbackLLMClient
and (b) was misreported as 'Failed to validate parsed CV'.
"""

import time

import pytest

from app.llm.exceptions import LLMAllKeysExhaustedError, LLMRateLimitError
from app.llm.key_rotator import KeyRotator


def test_rotates_among_available_keys():
    r = KeyRotator(["k1", "k2"])
    assert {r.get_key(), r.get_key()} == {"k1", "k2"}


def test_all_keys_daily_exhausted_raises_exhausted_not_attribute_error():
    r = KeyRotator(["k1", "k2"])
    r.mark_daily_exhausted("k1")
    r.mark_daily_exhausted("k2")
    with pytest.raises(LLMAllKeysExhaustedError):
        r.get_key()


def test_all_keys_rate_limited_raises_rate_limit_with_retry_hint():
    r = KeyRotator(["k1", "k2"])
    r.mark_rate_limited("k1", 60)
    r.mark_rate_limited("k2", 30)
    with pytest.raises(LLMRateLimitError) as exc_info:
        r.get_key()
    # Soonest available is the 30s one.
    assert 1 <= exc_info.value.retry_after_seconds <= 30


def test_exhausted_key_does_not_block_an_available_one():
    r = KeyRotator(["k1", "k2"])
    r.mark_daily_exhausted("k1")
    # Only k2 is available; every call should return it.
    assert r.get_key() == "k2"
    assert r.get_key() == "k2"


def test_key_recovers_after_rate_limit_window():
    r = KeyRotator(["k1"])
    r.mark_rate_limited("k1", 60)
    with pytest.raises(LLMRateLimitError):
        r.get_key()
    # Simulate the cooldown window elapsing (no real sleep).
    r._states_map["k1"].is_exhausted_until = time.time() - 1
    assert r.get_key() == "k1"
