from google import genai
from google.genai import types
from app.llm.base_client import BaseLLMClient
from app.config import Settings, settings as default_settings


class GeminiClient(BaseLLMClient):
    def __init__(self, settings: Settings = default_settings):
        self._settings = settings
        self._client = genai.Client(api_key=self._settings.gemini_api_key)
        self._model = self._settings.gemini_model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,
            ),
        )
        return response.text

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        return response.text