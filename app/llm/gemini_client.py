import re

from google import genai
from google.genai import types

from app.config import settings as default_settings
from app.llm.base_client import BaseLLMClient
from app.llm.key_rotator import _rotator


class GeminiClient(BaseLLMClient):
    def __init__(self):
        self._model = default_settings.gemini_model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self._call(system_prompt, user_prompt, json_mode=False)

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        return self._call(system_prompt, user_prompt, json_mode=True)

    def _call(self, system_prompt: str, user_prompt: str, json_mode: bool) -> str:
        key = _rotator.get_key()
        try:
            return self._generate(key, system_prompt, user_prompt, json_mode)
        except Exception as e:
            return self._handle_error(e, key, system_prompt, user_prompt, json_mode)

    def _generate(
        self, key: str, system_prompt: str, user_prompt: str, json_mode: bool
    ) -> str:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
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

    def _handle_error(
        self,
        e: Exception,
        key: str,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
    ) -> str:
        error_str = str(e)
        if "429" not in error_str:
            raise
        if "GenerateRequestsPerDay" in error_str or "per_day" in error_str.lower():
            _rotator.mark_daily_exhausted(key)
        else:
            _rotator.mark_rate_limited(key, self._parse_retry_after(error_str))

        return self._call(system_prompt, user_prompt, json_mode)

    def _parse_retry_after(self, error_str: str) -> int:
        match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_str, re.IGNORECASE)
        if match:
            return int(float(match.group(1))) + 5
        return 60
