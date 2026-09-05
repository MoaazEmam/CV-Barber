"""GroqClient: rate limits, daily exhaustion, and hard provider errors."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from groq import InternalServerError, NotFoundError, RateLimitError

from app.llm.exceptions import LLMAllKeysExhaustedError, LLMRateLimitError
from app.llm.groq_client import GroqClient

URL = "https://api.groq.com/openai/v1/chat/completions"


def _make_client(keys=None):
    return GroqClient(
        api_keys=keys if keys is not None else ["k1", "k2"],
        model="test-model",
    )


def _mock_completion(content="hello"):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


def _patch_sdk(client, side_effect=None, return_value=None):
    """Replace per-key AsyncGroq clients with a shared mock; return the mock."""
    create = AsyncMock(side_effect=side_effect, return_value=return_value)
    sdk = MagicMock()
    sdk.chat.completions.create = create
    client._client_for = lambda key: sdk
    return create


def _status_error(cls, status, message="boom", headers=None):
    request = httpx.Request("POST", URL)
    response = httpx.Response(status, request=request, headers=headers or {})
    return cls(message, response=response, body={"error": {"message": message}})


@pytest.mark.asyncio
async def test_returns_content_on_success():
    client = _make_client()
    _patch_sdk(client, return_value=_mock_completion("hi"))
    assert await client.complete("s", "u") == "hi"


@pytest.mark.asyncio
async def test_json_mode_sets_response_format():
    client = _make_client()
    create = _patch_sdk(client, return_value=_mock_completion("{}"))
    await client.complete_json("s", "u")
    assert create.await_args.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_model_not_found_parks_key_and_exhausts():
    """A retired model (404) must not escape as a raw error — it parks the key so
    ChainLLMClient falls through to the next provider."""
    client = _make_client(keys=["only"])
    _patch_sdk(
        client,
        side_effect=_status_error(
            NotFoundError, 404, "The model `llama-3.3-70b-versatile` does not exist"
        ),
    )
    with pytest.raises(LLMAllKeysExhaustedError):
        await client.complete("s", "u")


@pytest.mark.asyncio
async def test_model_not_found_tries_every_key_before_giving_up():
    client = _make_client(keys=["k1", "k2"])
    create = _patch_sdk(
        client, side_effect=_status_error(NotFoundError, 404, "model gone")
    )
    with pytest.raises(LLMAllKeysExhaustedError):
        await client.complete("s", "u")
    assert create.await_count == 2


@pytest.mark.asyncio
async def test_rate_limit_rotates_to_next_key():
    client = _make_client(keys=["k1", "k2"])
    _patch_sdk(
        client,
        side_effect=[
            _status_error(RateLimitError, 429, "slow down", headers={"retry-after": "5"}),
            _mock_completion("second key"),
        ],
    )
    assert await client.complete("s", "u") == "second key"


@pytest.mark.asyncio
async def test_daily_quota_exhausts_all_keys():
    client = _make_client(keys=["only"])
    _patch_sdk(
        client,
        side_effect=_status_error(
            RateLimitError, 429, "rate limit reached per day (RPD)"
        ),
    )
    with pytest.raises(LLMAllKeysExhaustedError):
        await client.complete("s", "u")


@pytest.mark.asyncio
async def test_upstream_5xx_surfaces_as_rate_limit():
    client = _make_client(keys=["only"])
    _patch_sdk(client, side_effect=_status_error(InternalServerError, 500, "oops"))
    with pytest.raises(LLMRateLimitError):
        await client.complete("s", "u")
