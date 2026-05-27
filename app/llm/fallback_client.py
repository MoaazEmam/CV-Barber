import structlog

from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import LLMAllKeysExhaustedError, LLMRateLimitError

log = structlog.get_logger()


class FallbackLLMClient(BaseLLMClient):
    """
    Wraps a primary and a fallback LLM client.

    If the primary raises LLMAllKeysExhaustedError (daily quota gone) or
    LLMRateLimitError (temporarily rate-limited), the same request is
    automatically retried on the fallback provider. If the fallback also
    fails, its exception propagates to the caller unchanged.

    This is transparent to all LLM callers (CVParser, CVScorer, etc.) —
    they only see a BaseLLMClient.
    """

    def __init__(self, primary: BaseLLMClient, fallback: BaseLLMClient):
        self._primary = primary
        self._fallback = fallback

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return await self._primary.complete(system_prompt, user_prompt)
        except (LLMAllKeysExhaustedError, LLMRateLimitError) as exc:
            log.warning(
                "primary_provider_unavailable_falling_back",
                reason=str(exc),
                fallback=type(self._fallback).__name__,
            )
            return await self._fallback.complete(system_prompt, user_prompt)

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return await self._primary.complete_json(system_prompt, user_prompt)
        except (LLMAllKeysExhaustedError, LLMRateLimitError) as exc:
            log.warning(
                "primary_provider_unavailable_falling_back",
                reason=str(exc),
                fallback=type(self._fallback).__name__,
            )
            return await self._fallback.complete_json(system_prompt, user_prompt)
