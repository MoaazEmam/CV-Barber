import structlog
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)

from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import LLMRateLimitError
from app.llm.key_rotator import KeyRotator

log = structlog.get_logger()

# retry-after values above this threshold (seconds) indicate a daily quota
# exhaustion rather than a short per-minute rate limit.
_DAILY_EXHAUSTION_THRESHOLD_SECONDS = 3600

# Sentinel for providers that accept unauthenticated requests (e.g. LLM7).
KEYLESS_SENTINEL = "__keyless__"


def _key_index(rotator: KeyRotator, key: str) -> int:
    try:
        return list(rotator._states_map.keys()).index(key)
    except ValueError:
        return -1


class OpenAICompatibleClient(BaseLLMClient):
    """
    Generic async client for any provider exposing an OpenAI-compatible
    chat-completions endpoint (Cerebras, NVIDIA NIM, Mistral, OpenRouter,
    LLM7, Z AI, ...). Mirrors GroqClient's key rotation and
    rate-limit / daily-exhaustion handling.
    """

    def __init__(
        self,
        base_url: str,
        api_keys: list[str],
        model: str,
        provider_name: str,
        supports_json_mode: bool = True,
        rotator: KeyRotator | None = None,
    ):
        keys = api_keys or [KEYLESS_SENTINEL]
        self._base_url = base_url
        self._model = model
        self._provider = provider_name
        self._supports_json_mode = supports_json_mode
        self._rotator = rotator or KeyRotator(keys)
        self._clients: dict[str, AsyncOpenAI] = {}

    def _client_for(self, key: str) -> AsyncOpenAI:
        if key not in self._clients:
            self._clients[key] = AsyncOpenAI(api_key=key, base_url=self._base_url)
        return self._clients[key]

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        return await self._call(system_prompt, user_prompt, json_mode=False)

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        if not self._supports_json_mode:
            # Prompt-enforced JSON via BaseLLMClient.
            return await super().complete_json(system_prompt, user_prompt)
        return await self._call(system_prompt, user_prompt, json_mode=True)

    async def _call(self, system_prompt: str, user_prompt: str, json_mode: bool) -> str:
        key = self._rotator.get_key()  # raises LLMRateLimitError / LLMAllKeysExhaustedError
        key_idx = _key_index(self._rotator, key)
        log.info(
            "llm_call",
            provider=self._provider,
            key_index=key_idx,
            json_mode=json_mode,
            model=self._model,
        )

        kwargs: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await self._client_for(key).chat.completions.create(**kwargs)
            return response.choices[0].message.content

        except (APITimeoutError, APIConnectionError):
            log.warning("llm_timeout", provider=self._provider, key_index=key_idx)
            raise LLMRateLimitError(retry_after_seconds=30)

        except RateLimitError as exc:
            return await self._handle_rate_limit(
                exc, key, system_prompt, user_prompt, json_mode
            )

        except InternalServerError:
            log.warning("llm_upstream_error", provider=self._provider, key_index=key_idx)
            raise LLMRateLimitError(retry_after_seconds=30)

        except APIStatusError as exc:
            # Hard 4xx (404 unknown model, 401/403 bad key, ...): the provider is
            # misconfigured, not busy. Park this key until midnight so the chain
            # skips the provider and falls through instead of dying here.
            log.error(
                "llm_provider_error",
                provider=self._provider,
                key_index=key_idx,
                status=exc.status_code,
                detail=str(exc)[:200],
            )
            self._rotator.mark_daily_exhausted(key)
            return await self._call(system_prompt, user_prompt, json_mode)

    async def _handle_rate_limit(
        self,
        exc: RateLimitError,
        key: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
    ) -> str:
        key_idx = _key_index(self._rotator, key)

        try:
            retry_after = int(float(exc.response.headers.get("retry-after", 60)))
        except (TypeError, ValueError, AttributeError):
            retry_after = 60

        error_msg = ""
        if isinstance(exc.body, dict):
            error = exc.body.get("error", {})
            if isinstance(error, dict):
                error_msg = str(error.get("message", "")).lower()
            else:
                error_msg = str(error).lower()

        is_daily = (
            retry_after > _DAILY_EXHAUSTION_THRESHOLD_SECONDS
            or "per day" in error_msg
            or "daily" in error_msg
            or "quota" in error_msg
        )

        if is_daily:
            log.warning(
                "llm_key_daily_exhausted", provider=self._provider, key_index=key_idx
            )
            self._rotator.mark_daily_exhausted(key)
        else:
            log.warning(
                "llm_key_rate_limited",
                provider=self._provider,
                key_index=key_idx,
                retry_after=retry_after,
            )
            self._rotator.mark_rate_limited(key, retry_after)

        # Recurse — KeyRotator picks the next available key,
        # or raises LLMRateLimitError / LLMAllKeysExhaustedError if none remain.
        return await self._call(system_prompt, user_prompt, json_mode)
