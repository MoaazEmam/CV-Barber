from app.llm.base_client import BaseLLMClient
from app.config import settings


class LLMClientFactory:
    @staticmethod
    def create() -> BaseLLMClient:
        provider = settings.llm_provider.lower()

        if provider == "groq":
            from app.llm.groq_client import GroqClient
            groq_keys = settings.get_all_groq_keys()
            if not groq_keys:
                raise ValueError(
                    "LLM_PROVIDER=groq but no Groq API keys are configured. "
                    "Set GROQ_API_KEY or GROQ_API_KEYS in your .env file."
                )
            primary = GroqClient(groq_keys, settings.groq_model)

            # Wrap in FallbackLLMClient if real Gemini keys are also configured.
            gemini_keys = settings.get_all_gemini_keys()
            if gemini_keys:
                from app.llm.gemini_client import GeminiClient
                from app.llm.fallback_client import FallbackLLMClient
                return FallbackLLMClient(primary, GeminiClient())

            return primary

        if provider == "gemini":
            from app.llm.gemini_client import GeminiClient
            return GeminiClient()

        if provider == "ollama":
            from app.llm.ollama_client import OllamaClient
            return OllamaClient()

        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            "Valid options: 'groq', 'gemini', 'ollama'"
        )
