"""OpenAICompatibleClient: rotation, rate limits, daily exhaustion, JSON modes."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import RateLimitError

from app.llm.exceptions import LLMAllKeysExhaustedError
from app.llm.openai_compat_client import KEYLESS_SENTINEL, OpenAICompatibleClient


def _make_client(keys=None, supports_json_mode=True):
    return OpenAICompatibleClient(
        base_url="https://example.test/v1",
        api_keys=keys if keys is not None else ["k1", "k2"],
        model="test-model",
        provider_name="testprov",
        supports_json_mode=supports_json_mode,
    )


def _mock_completion(content="hello"):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


def _patch_sdk(client, side_effect=None, return_value=None):
    """Replace per-key AsyncOpenAI clients with a shared mock; return the mock."""
    create = AsyncMock(side_effect=side_effect, return_value=return_value)
    sdk = MagicMock()
    sdk.chat.completions.create = create
    client._client_for = lambda key: sdk
    return create


def _rate_limit_error(retry_after="5", message="too many requests"):
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(
        429, headers={"retry-after": retry_after}, request=request
    )
    return RateLimitError(
        message, response=response, body={"error": {"message": message}}
    )


@pytest.mark.asyncio
async def test_success_returns_content():
    client = _make_client()
    _patch_sdk(client, return_value=_mock_completion("hi"))
    assert await client.complete("s", "u") == "hi"


@pytest.mark.asyncio
async def test_429_rotates_to_next_key():
    client = _make_client()
    create = _patch_sdk(
        client, side_effect=[_rate_limit_error(), _mock_completion("recovered")]
    )
    assert await client.complete("s", "u") == "recovered"
    assert create.await_count == 2


@pytest.mark.asyncio
async def test_daily_exhaustion_marks_all_keys():
    client = _make_client(keys=["only"])
    _patch_sdk(
        client, side_effect=_rate_limit_error(message="you exceeded your daily limit")
    )
    with pytest.raises(LLMAllKeysExhaustedError):
        await client.complete("s", "u")


@pytest.mark.asyncio
async def test_large_retry_after_treated_as_daily():
    client = _make_client(keys=["only"])
    _patch_sdk(client, side_effect=_rate_limit_error(retry_after="86400"))
    with pytest.raises(LLMAllKeysExhaustedError):
        await client.complete("s", "u")


@pytest.mark.asyncio
async def test_hard_api_error_parks_key_and_exhausts():
    """404/401-style errors mark the key daily-exhausted so the chain falls through."""
    from openai import NotFoundError

    client = _make_client(keys=["only"])
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(404, request=request)
    _patch_sdk(
        client,
        side_effect=NotFoundError(
            "model does not exist", response=response, body={"message": "nope"}
        ),
    )
    with pytest.raises(LLMAllKeysExhaustedError):
        await client.complete("s", "u")


def test_keyless_construction_uses_sentinel():
    client = _make_client(keys=[])
    assert list(client._rotator._states_map.keys()) == [KEYLESS_SENTINEL]


@pytest.mark.asyncio
async def test_native_json_mode_sets_response_format():
    client = _make_client(supports_json_mode=True)
    create = _patch_sdk(client, return_value=_mock_completion("{}"))
    await client.complete_json("s", "u")
    assert create.await_args.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_prompt_enforced_json_when_unsupported():
    client = _make_client(supports_json_mode=False)
    create = _patch_sdk(client, return_value=_mock_completion("{}"))
    await client.complete_json("s", "u")
    kwargs = create.await_args.kwargs
    assert "response_format" not in kwargs
    assert "valid JSON only" in kwargs["messages"][0]["content"]
