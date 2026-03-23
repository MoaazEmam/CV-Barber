from app.llm.base_client import BaseLLMClient
from app.config import settings


class LLMClientFactory:
    @staticmethod
    def create() -> BaseLLMClient:
        provider = settings.llm_provider.lower()

        if provider == "gemini":
            from app.llm.gemini_client import GeminiClient
            return GeminiClient()

        if provider == "ollama":
            from app.llm.ollama_client import OllamaClient
            return OllamaClient()

        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            "Valid options: 'gemini', 'ollama'"
        )