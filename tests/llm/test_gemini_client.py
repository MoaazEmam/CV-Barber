"""GeminiClient error classification: transient vs. fatal-for-this-provider."""

from unittest.mock import AsyncMock

import pytest

from app.llm.exceptions import LLMAllKeysExhaustedError, LLMRateLimitError
from app.llm.gemini_client import GeminiClient


def _make_client(keys=None):
    return GeminiClient(api_keys=keys if keys is not None else ["k1", "k2"])


def _patch_generate(client, side_effect=None, return_value=None):
    generate = AsyncMock(side_effect=side_effect, return_value=return_value)
    client._generate = generate
    return generate


@pytest.mark.asyncio
async def test_returns_text_on_success():
    client = _make_client()
    _patch_generate(client, return_value="hi")
    assert await client.complete("s", "u") == "hi"


@pytest.mark.asyncio
async def test_model_not_found_parks_key_and_exhausts():
    """A retired model (404) must not escape as a raw error — it parks the key so
    ChainLLMClient falls through to the next provider."""
    client = _make_client(keys=["only"])
    _patch_generate(
        client,
        side_effect=Exception("404 NOT_FOUND models/gemini-2.5-flash is not found"),
    )
    with pytest.raises(LLMAllKeysExhaustedError):
        await client.complete("s", "u")


@pytest.mark.asyncio
async def test_bad_key_parks_key_and_exhausts():
    client = _make_client(keys=["only"])
    _patch_generate(
        client, side_effect=Exception("403 PERMISSION_DENIED API key not valid")
    )
    with pytest.raises(LLMAllKeysExhaustedError):
        await client.complete("s", "u")


@pytest.mark.asyncio
async def test_provider_error_tries_every_key_before_giving_up():
    client = _make_client(keys=["k1", "k2"])
    generate = _patch_generate(client, side_effect=Exception("404 NOT_FOUND"))
    with pytest.raises(LLMAllKeysExhaustedError):
        await client.complete("s", "u")
    assert generate.await_count == 2


@pytest.mark.asyncio
async def test_upstream_unavailable_surfaces_as_rate_limit():
    client = _make_client(keys=["only"])
    _patch_generate(client, side_effect=Exception("503 UNAVAILABLE model overloaded"))
    with pytest.raises(LLMRateLimitError):
        await client.complete("s", "u")


@pytest.mark.asyncio
async def test_rate_limit_rotates_to_next_key():
    client = _make_client(keys=["k1", "k2"])
    _patch_generate(
        client,
        side_effect=[Exception("429 RESOURCE_EXHAUSTED, retry in 5s"), "second key"],
    )
    assert await client.complete("s", "u") == "second key"


@pytest.mark.asyncio
async def test_unrecognised_error_still_propagates():
    """A genuine bug must not be silently swallowed as a provider outage."""
    client = _make_client(keys=["only"])
    _patch_generate(client, side_effect=TypeError("programming error"))
    with pytest.raises(TypeError):
        await client.complete("s", "u")
