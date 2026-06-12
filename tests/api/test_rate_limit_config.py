"""The per-user LLM limit string comes from settings and is SlowAPI-parseable."""

from limits import parse_many

from app.api.rate_limit import LLM_USER_LIMITS
from app.config import settings


def test_llm_limits_read_from_settings():
    assert LLM_USER_LIMITS == settings.llm_user_rate_limits


def test_llm_limits_parse_and_include_burst_guard():
    parsed = parse_many(LLM_USER_LIMITS)
    granularities = {item.GRANULARITY.name for item in parsed}
    # A per-minute window must exist — it's the actual anti-burst control.
    assert "minute" in granularities
    assert "day" in granularities
