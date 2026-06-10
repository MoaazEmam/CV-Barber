from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    """Static description of an OpenAI-compatible provider endpoint."""

    base_url: str
    # Whether the endpoint reliably supports response_format={"type": "json_object"}.
    # When False, the prompt-enforced JSON fallback from BaseLLMClient is used.
    json_mode: bool = False
    # Provider accepts requests without an API key (e.g. LLM7).
    keyless_ok: bool = False


# OpenAI-compatible providers served by OpenAICompatibleClient.
# groq and gemini are not listed here — they keep their dedicated clients.
PROVIDERS: dict[str, ProviderSpec] = {
    "cerebras": ProviderSpec(base_url="https://api.cerebras.ai/v1", json_mode=True),
    "nvidia": ProviderSpec(base_url="https://integrate.api.nvidia.com/v1"),
    "mistral": ProviderSpec(base_url="https://api.mistral.ai/v1", json_mode=True),
    "openrouter": ProviderSpec(base_url="https://openrouter.ai/api/v1"),
    "llm7": ProviderSpec(base_url="https://api.llm7.io/v1", keyless_ok=True),
    "zai": ProviderSpec(base_url="https://api.z.ai/api/paas/v4"),
}
