import threading

from app.config import settings
from app.llm.base_client import BaseLLMClient
from app.llm.key_rotator import KeyRotator

# Provider priority per profile. Interactive routes (parse/tailor/QA/...) lead
# with Groq; background tasks (ATS scoring) lead with Cerebras/Mistral so they
# don't compete for the interactive Groq budget. "groq_small" is a
# pseudo-provider: the Groq endpoint with the cheaper model, sharing the same
# rotator (rate limits are per account, not per model).
INTERACTIVE_ORDER = ["groq", "gemini", "nvidia", "mistral", "openrouter", "llm7", "zai"]
BACKGROUND_ORDER = ["cerebras", "mistral", "groq_small"] + INTERACTIVE_ORDER

# One rotator per provider (shared across models) and one client per
# provider:model, so every caller in the process shares rate-limit state.
_rotators: dict[str, KeyRotator] = {}
_clients: dict[str, BaseLLMClient] = {}
_lock = threading.Lock()


def _rotator_for(provider: str, keys: list[str]) -> KeyRotator:
    if provider not in _rotators:
        _rotators[provider] = KeyRotator(keys)
    return _rotators[provider]


def _build_leaf(provider: str) -> BaseLLMClient | None:
    """Build (or fetch cached) client for one provider; None if not configured."""
    if provider in ("groq", "groq_small"):
        keys = settings.get_all_groq_keys()
        if not keys:
            return None
        model = settings.groq_small_model if provider == "groq_small" else settings.groq_model
        cache_key = f"groq:{model}"
        if cache_key not in _clients:
            from app.llm.groq_client import GroqClient

            _clients[cache_key] = GroqClient(keys, model, rotator=_rotator_for("groq", keys))
        return _clients[cache_key]

    if provider == "gemini":
        keys = settings.get_all_gemini_keys()
        if not keys:
            return None
        cache_key = f"gemini:{settings.gemini_model}"
        if cache_key not in _clients:
            from app.llm.gemini_client import GeminiClient

            _clients[cache_key] = GeminiClient(keys, rotator=_rotator_for("gemini", keys))
        return _clients[cache_key]

    from app.llm.providers import PROVIDERS

    spec = PROVIDERS.get(provider)
    if spec is None:
        raise ValueError(f"Unknown LLM provider '{provider}' in chain configuration.")

    keys = settings.get_provider_keys(provider)
    if not keys:
        # Keyless providers join only when explicitly enabled (LLM7) — absence
        # of a key cannot signal intent for them.
        if not (spec.keyless_ok and provider == "llm7" and settings.llm7_enabled):
            return None

    model = getattr(settings, f"{provider}_model")
    cache_key = f"{provider}:{model}"
    if cache_key not in _clients:
        from app.llm.openai_compat_client import OpenAICompatibleClient

        _clients[cache_key] = OpenAICompatibleClient(
            base_url=spec.base_url,
            api_keys=keys,
            model=model,
            provider_name=provider,
            supports_json_mode=spec.json_mode,
            rotator=_rotator_for(provider, keys or ["__keyless__"]),
        )
    return _clients[cache_key]


def _chain_order(profile: str) -> list[str]:
    override = (
        settings.llm_interactive_chain
        if profile == "interactive"
        else settings.llm_background_chain
    )
    if override:
        order = [p.strip().lower() for p in override.split(",") if p.strip()]
    else:
        order = INTERACTIVE_ORDER if profile == "interactive" else BACKGROUND_ORDER
    deduped: list[str] = []
    for p in order:
        if p not in deduped:
            deduped.append(p)
    return deduped


class LLMClientFactory:
    @staticmethod
    def create(profile: str = "interactive") -> BaseLLMClient:
        provider = settings.llm_provider.lower()

        # Legacy escape hatches: a single explicit provider, no chain.
        if provider == "gemini":
            client = _build_leaf("gemini")
            if client is None:
                raise ValueError(
                    "LLM_PROVIDER=gemini but no Gemini API keys are configured. "
                    "Set GEMINI_API_KEY or GEMINI_API_KEYS in your .env file."
                )
            return client

        if provider == "ollama":
            from app.llm.ollama_client import OllamaClient

            return OllamaClient()

        if provider != "groq":
            raise ValueError(
                f"Unknown LLM provider '{provider}'. "
                "Valid options: 'groq', 'gemini', 'ollama'"
            )

        with _lock:
            clients = []
            for name in _chain_order(profile):
                leaf = _build_leaf(name)
                if leaf is not None and leaf not in clients:
                    clients.append(leaf)

        if not clients:
            raise ValueError(
                "No LLM API keys are configured. Set GROQ_API_KEY/GROQ_API_KEYS "
                "(or any other provider's *_API_KEYS) in your .env file."
            )

        if len(clients) == 1:
            return clients[0]

        from app.llm.chain_client import ChainLLMClient

        return ChainLLMClient(clients)
