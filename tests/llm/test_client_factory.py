"""LLMClientFactory: auto-detection, chain ordering, caching, profiles."""

import pytest

import app.llm.client_factory as factory_mod
from app.llm.chain_client import ChainLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.gemini_client import GeminiClient
from app.llm.groq_client import GroqClient
from app.llm.openai_compat_client import OpenAICompatibleClient


@pytest.fixture(autouse=True)
def clean_factory(monkeypatch):
    """Reset factory caches and blank out every provider's keys."""
    monkeypatch.setattr(factory_mod, "_rotators", {})
    monkeypatch.setattr(factory_mod, "_clients", {})
    settings = factory_mod.settings
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "groq_api_keys", None)
    monkeypatch.setattr(settings, "gemini_api_key", "def_key")
    monkeypatch.setattr(settings, "gemini_api_keys", "")
    for provider in ("cerebras", "nvidia", "mistral", "openrouter", "llm7", "zai"):
        monkeypatch.setattr(settings, f"{provider}_api_keys", None)
    monkeypatch.setattr(settings, "llm7_enabled", False)
    monkeypatch.setattr(settings, "llm_interactive_chain", None)
    monkeypatch.setattr(settings, "llm_background_chain", None)
    yield monkeypatch


def test_no_keys_raises():
    with pytest.raises(ValueError):
        LLMClientFactory.create()


def test_groq_only_returns_bare_client(clean_factory):
    clean_factory.setattr(factory_mod.settings, "groq_api_keys", "gk1,gk2")
    client = LLMClientFactory.create()
    assert isinstance(client, GroqClient)


def test_groq_plus_gemini_builds_two_chain(clean_factory):
    clean_factory.setattr(factory_mod.settings, "groq_api_keys", "gk1")
    clean_factory.setattr(factory_mod.settings, "gemini_api_keys", "gm1")
    client = LLMClientFactory.create()
    assert isinstance(client, ChainLLMClient)
    assert isinstance(client._clients[0], GroqClient)
    assert isinstance(client._clients[1], GeminiClient)


def test_auto_detection_adds_configured_providers_in_order(clean_factory):
    clean_factory.setattr(factory_mod.settings, "groq_api_keys", "gk1")
    clean_factory.setattr(factory_mod.settings, "mistral_api_keys", "mk1")
    clean_factory.setattr(factory_mod.settings, "nvidia_api_keys", "nk1")
    client = LLMClientFactory.create()
    assert isinstance(client, ChainLLMClient)
    types = [type(c).__name__ for c in client._clients]
    assert types == ["GroqClient", "OpenAICompatibleClient", "OpenAICompatibleClient"]
    # nvidia precedes mistral in INTERACTIVE_ORDER
    assert client._clients[1]._provider == "nvidia"
    assert client._clients[2]._provider == "mistral"


def test_single_non_groq_provider_returns_bare_client(clean_factory):
    clean_factory.setattr(factory_mod.settings, "mistral_api_keys", "mk1")
    client = LLMClientFactory.create()
    assert isinstance(client, OpenAICompatibleClient)
    assert client._provider == "mistral"


def test_background_profile_leads_with_cerebras(clean_factory):
    clean_factory.setattr(factory_mod.settings, "groq_api_keys", "gk1")
    clean_factory.setattr(factory_mod.settings, "cerebras_api_keys", "ck1")
    client = LLMClientFactory.create("background")
    assert isinstance(client, ChainLLMClient)
    assert client._clients[0]._provider == "cerebras"
    # then groq_small, then groq (both GroqClient with different models)
    assert isinstance(client._clients[1], GroqClient)
    assert isinstance(client._clients[2], GroqClient)
    assert client._clients[1]._model != client._clients[2]._model


def test_groq_and_groq_small_share_rotator(clean_factory):
    clean_factory.setattr(factory_mod.settings, "groq_api_keys", "gk1")
    client = LLMClientFactory.create("background")
    small, big = client._clients[0], client._clients[1]
    assert small._rotator is big._rotator


def test_chain_order_env_override(clean_factory):
    clean_factory.setattr(factory_mod.settings, "groq_api_keys", "gk1")
    clean_factory.setattr(factory_mod.settings, "mistral_api_keys", "mk1")
    clean_factory.setattr(
        factory_mod.settings, "llm_interactive_chain", "mistral,groq"
    )
    client = LLMClientFactory.create()
    assert client._clients[0]._provider == "mistral"
    assert isinstance(client._clients[1], GroqClient)


def test_clients_are_cached_across_create_calls(clean_factory):
    clean_factory.setattr(factory_mod.settings, "groq_api_keys", "gk1")
    a = LLMClientFactory.create()
    b = LLMClientFactory.create()
    assert a is b


def test_llm7_excluded_unless_enabled(clean_factory):
    clean_factory.setattr(factory_mod.settings, "groq_api_keys", "gk1")
    client = LLMClientFactory.create()
    assert isinstance(client, GroqClient)

    clean_factory.setattr(factory_mod.settings, "llm7_enabled", True)
    clean_factory.setattr(factory_mod, "_clients", {})
    clean_factory.setattr(factory_mod, "_rotators", {})
    client = LLMClientFactory.create()
    assert isinstance(client, ChainLLMClient)
    assert client._clients[1]._provider == "llm7"


def test_legacy_gemini_provider_escape_hatch(clean_factory):
    clean_factory.setattr(factory_mod.settings, "llm_provider", "gemini")
    clean_factory.setattr(factory_mod.settings, "gemini_api_keys", "gm1")
    client = LLMClientFactory.create()
    assert isinstance(client, GeminiClient)
