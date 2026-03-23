import requests
import json
from app.llm.base_client import BaseLLMClient
from app.config import settings


class OllamaClient(BaseLLMClient):
    def __init__(self):
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = requests.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.1},
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Override to use Ollama's native JSON format mode.
        """
        response = requests.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1},
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]