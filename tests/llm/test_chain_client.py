"""ChainLLMClient walks the provider list on rate-limit/exhaustion errors."""

from unittest.mock import AsyncMock

import pytest

from app.llm.base_client import BaseLLMClient
from app.llm.chain_client import ChainLLMClient
from app.llm.exceptions import LLMAllKeysExhaustedError, LLMRateLimitError


def _client(result=None, error=None):
    client = AsyncMock(spec=BaseLLMClient)
    if error is not None:
        client.complete.side_effect = error
        client.complete_json.side_effect = error
    else:
        client.complete.return_value = result
        client.complete_json.return_value = result
    return client


@pytest.mark.asyncio
async def test_returns_first_success():
    first = _client(result="first")
    second = _client(result="second")
    chain = ChainLLMClient([first, second])

    assert await chain.complete("s", "u") == "first"
    second.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_falls_through_on_rate_limit():
    chain = ChainLLMClient(
        [_client(error=LLMRateLimitError(retry_after_seconds=30)), _client(result="ok")]
    )
    assert await chain.complete("s", "u") == "ok"


@pytest.mark.asyncio
async def test_falls_through_on_daily_exhaustion():
    chain = ChainLLMClient(
        [_client(error=LLMAllKeysExhaustedError("gone")), _client(result="ok")]
    )
    assert await chain.complete("s", "u") == "ok"


@pytest.mark.asyncio
async def test_raises_last_error_when_all_fail():
    last_error = LLMAllKeysExhaustedError("last")
    chain = ChainLLMClient(
        [
            _client(error=LLMRateLimitError(retry_after_seconds=10)),
            _client(error=last_error),
        ]
    )
    with pytest.raises(LLMAllKeysExhaustedError):
        await chain.complete("s", "u")


@pytest.mark.asyncio
async def test_complete_json_walks_chain():
    first = _client(error=LLMRateLimitError(retry_after_seconds=5))
    second = _client(result='{"ok": true}')
    chain = ChainLLMClient([first, second])

    assert await chain.complete_json("s", "u") == '{"ok": true}'
    first.complete_json.assert_awaited_once()
    second.complete_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_chain_errors_propagate_immediately():
    second = _client(result="ok")
    chain = ChainLLMClient([_client(error=ValueError("boom")), second])
    with pytest.raises(ValueError):
        await chain.complete("s", "u")
    second.complete.assert_not_awaited()


def test_empty_chain_rejected():
    with pytest.raises(ValueError):
        ChainLLMClient([])
