import re

import structlog
from google import genai
from google.genai import types

from app.config import settings as default_settings
from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import LLMRateLimitError
from app.llm.key_rotator import KeyRotator

log = structlog.get_logger()


# Status codes / statuses that mean "this provider will never serve this request"
# — as opposed to a transient 429/5xx that is worth retrying on another key.
_PROVIDER_ERROR_MARKERS = (
    "400",
    "401",
    "403",
    "404",
    "INVALID_ARGUMENT",
    "PERMISSION_DENIED",
    "NOT_FOUND",
    "UNAUTHENTICATED",
)


def _is_provider_error(error_str: str) -> bool:
    return any(marker in error_str for marker in _PROVIDER_ERROR_MARKERS)


def _key_index(rotator: KeyRotator, key: str) -> int:
    try:
        return list(rotator._states_map.keys()).index(key)
    except ValueError:
        return -1


class GeminiClient(BaseLLMClient):
    def __init__(
        self,
        api_keys: list[str] | None = None,
        rotator: KeyRotator | None = None,
    ):
        self._model = default_settings.gemini_model
        keys = api_keys or default_settings.get_all_gemini_keys()
        self._rotator = rotator or KeyRotator(keys)

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        return await self._call(system_prompt, user_prompt, json_mode=False)

    async def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        return await self._call(system_prompt, user_prompt, json_mode=True)

    async def _call(
        self, system_prompt: str, user_prompt: str, json_mode: bool
    ) -> str:
        key = self._rotator.get_key()
        log.info(
            "gemini_call",
            key_index=_key_index(self._rotator, key),
            json_mode=json_mode,
        )
        try:
            return await self._generate(key, system_prompt, user_prompt, json_mode)
        except Exception as e:
            return await self._handle_error(
                e, key, system_prompt, user_prompt, json_mode
            )

    async def _generate(
        self, key: str, system_prompt: str, user_prompt: str, json_mode: bool
    ) -> str:
        client = genai.Client(api_key=key)
        response = await client.aio.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=self._build_config(system_prompt, json_mode),
        )
        return response.text

    def _build_config(
        self, system_prompt: str, json_mode: bool
    ) -> types.GenerateContentConfig:
        config_kwargs = {
            "system_instruction": system_prompt,
            "temperature": 0.1,
        }
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        return types.GenerateContentConfig(**config_kwargs)

    async def _handle_error(
        self,
        e: Exception,
        key: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
    ) -> str:
        error_str = str(e)
        key_idx = _key_index(self._rotator, key)
        # Upstream transient errors (503 model overloaded, 500, 502, 504) → surface as rate-limit
        # so the API layer returns a clean 429 with a retry hint rather than a raw 500.
        if any(code in error_str for code in ("503", "502", "504", "UNAVAILABLE")):
            log.warning("gemini_upstream_unavailable", key_index=key_idx)
            raise LLMRateLimitError(retry_after_seconds=30) from e
        # Hard client errors (404 retired/unknown model, 401/403 bad key, 400 bad
        # request): Gemini is misconfigured, not busy. Park this key until midnight
        # so the chain skips the provider and falls through instead of dying here.
        if _is_provider_error(error_str):
            log.error("gemini_provider_error", key_index=key_idx, detail=error_str[:200])
            self._rotator.mark_daily_exhausted(key)
            return await self._call(system_prompt, user_prompt, json_mode)
        if "429" not in error_str:
            raise
        if "GenerateRequestsPerDay" in error_str or "per_day" in error_str.lower():
            log.warning("gemini_key_daily_exhausted", key_index=key_idx)
            self._rotator.mark_daily_exhausted(key)
        else:
            retry_after = self._parse_retry_after(error_str)
            log.warning(
                "gemini_key_rate_limited",
                key_index=key_idx,
                retry_after=retry_after,
            )
            self._rotator.mark_rate_limited(key, retry_after)

        return await self._call(system_prompt, user_prompt, json_mode)

    def _parse_retry_after(self, error_str: str) -> int:
        match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_str, re.IGNORECASE)
        if match:
            return int(float(match.group(1))) + 5
        return 60
