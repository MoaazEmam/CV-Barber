import structlog

from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import LLMAllKeysExhaustedError, LLMRateLimitError

log = structlog.get_logger()


class ChainLLMClient(BaseLLMClient):
    """
    Walks an ordered list of LLM clients. When one raises
    LLMRateLimitError or LLMAllKeysExhaustedError, the same request is
    retried on the next client in the chain. If every client fails, the
    last error propagates unchanged so the API layer keeps its existing
    429/503 mapping.

    Transparent to all LLM callers — they only see a BaseLLMClient.
    """

    def __init__(self, clients: list[BaseLLMClient]):
        if not clients:
            raise ValueError("ChainLLMClient requires at least one client")
        self._clients = clients

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        return await self._walk("complete", system_prompt, user_prompt)

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        return await self._walk("complete_json", system_prompt, user_prompt)

    async def _walk(self, method: str, system_prompt: str, user_prompt: str) -> str:
        last_exc: Exception | None = None
        for client in self._clients:
            try:
                return await getattr(client, method)(system_prompt, user_prompt)
            except (LLMRateLimitError, LLMAllKeysExhaustedError) as exc:
                log.warning(
                    "llm_chain_fallback",
                    failed=type(client).__name__,
                    reason=str(exc),
                )
                last_exc = exc
        raise last_exc
