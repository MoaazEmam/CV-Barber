import structlog
from groq import AsyncGroq
from groq import (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)

from app.llm.base_client import BaseLLMClient
from app.llm.key_rotator import KeyRotator
from app.llm.exceptions import LLMRateLimitError

log = structlog.get_logger()

# retry-after values above this threshold (seconds) indicate a daily quota
# exhaustion rather than a short per-minute rate limit.
_DAILY_EXHAUSTION_THRESHOLD_SECONDS = 3600


def _key_index(rotator: KeyRotator, key: str) -> int:
    try:
        return list(rotator._states_map.keys()).index(key)
    except ValueError:
        return -1


class GroqClient(BaseLLMClient):
    """
    Async LLM client for the Groq inference API using the official groq Python SDK.
    Uses a KeyRotator to round-robin across multiple API keys and handles
    per-minute rate limits and daily quota exhaustion identically to GeminiClient.
    """

    def __init__(
        self, api_keys: list[str], model: str, rotator: KeyRotator | None = None
    ):
        # An externally supplied rotator lets multiple clients (e.g. the big and
        # small Groq models) share rate-limit state — limits are per account.
        self._rotator = rotator or KeyRotator(api_keys)
        self._model = model
        # Cache one AsyncGroq client per key to reuse the underlying httpx connection pool.
        self._clients: dict[str, AsyncGroq] = {
            key: AsyncGroq(api_key=key) for key in api_keys
        }

    def _client_for(self, key: str) -> AsyncGroq:
        # Handles the edge case where a new key appears after construction.
        if key not in self._clients:
            self._clients[key] = AsyncGroq(api_key=key)
        return self._clients[key]

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        return await self._call(system_prompt, user_prompt, json_mode=False)

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        return await self._call(system_prompt, user_prompt, json_mode=True)

    def _build_messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    async def _call(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
    ) -> str:
        key = self._rotator.get_key()  # raises LLMRateLimitError / LLMAllKeysExhaustedError
        key_idx = _key_index(self._rotator, key)
        log.info(
            "groq_call",
            key_index=key_idx,
            json_mode=json_mode,
            model=self._model,
        )

        kwargs: dict = {
            "model": self._model,
            "messages": self._build_messages(system_prompt, user_prompt),
            "temperature": 0.1,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await self._client_for(key).chat.completions.create(**kwargs)
            return response.choices[0].message.content

        except (APITimeoutError, APIConnectionError):
            # Network-level failure — treat as a short backoff, not a key problem.
            log.warning("groq_timeout", key_index=key_idx)
            raise LLMRateLimitError(retry_after_seconds=30)

        except RateLimitError as exc:
            return await self._handle_rate_limit(
                exc, key, system_prompt, user_prompt, json_mode
            )

        except InternalServerError:
            # 5xx from Groq upstream — surface as a short backoff.
            log.warning("groq_upstream_error", key_index=key_idx)
            raise LLMRateLimitError(retry_after_seconds=30)

    async def _handle_rate_limit(
        self,
        exc: RateLimitError,
        key: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
    ) -> str:
        key_idx = _key_index(self._rotator, key)

        # retry-after header gives seconds to wait (present on 429 responses).
        retry_after = int(exc.response.headers.get("retry-after", 60))

        # Groq's 429 body: {"error": {"message": "...", "type": "...", "code": "..."}}
        error_msg = ""
        if isinstance(exc.body, dict):
            error_msg = exc.body.get("error", {}).get("message", "").lower()

        # Daily quota exhaustion: very large retry-after OR body mentions "per day"/RPD/TPD.
        is_daily = (
            retry_after > _DAILY_EXHAUSTION_THRESHOLD_SECONDS
            or "per day" in error_msg
            or " rpd" in error_msg
            or " tpd" in error_msg
            or "daily" in error_msg
        )

        if is_daily:
            log.warning("groq_key_daily_exhausted", key_index=key_idx)
            self._rotator.mark_daily_exhausted(key)
        else:
            log.warning(
                "groq_key_rate_limited", key_index=key_idx, retry_after=retry_after
            )
            self._rotator.mark_rate_limited(key, retry_after)

        # Recurse — KeyRotator picks the next available key,
        # or raises LLMRateLimitError / LLMAllKeysExhaustedError if none remain.
        return await self._call(system_prompt, user_prompt, json_mode)
