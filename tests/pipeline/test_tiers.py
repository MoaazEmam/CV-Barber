"""Tier client selection."""

import app.llm.client_factory as factory_mod
from app.llm.groq_client import GroqClient
from app.pipeline import tiers


def test_tier1_client_is_groq_factory(monkeypatch):
    # client_factory reads the same settings singleton as tiers.
    monkeypatch.setattr(factory_mod, "_rotators", {})
    monkeypatch.setattr(factory_mod, "_clients", {})
    monkeypatch.setattr(tiers.settings, "llm_provider", "groq")
    monkeypatch.setattr(tiers.settings, "groq_api_keys", "k1")
    monkeypatch.setattr(tiers.settings, "gemini_api_keys", "")
    monkeypatch.setattr(tiers.settings, "gemini_api_key", "def_key")
    # Blank every optional provider so the local .env can't grow the chain.
    for provider in ("cerebras", "nvidia", "mistral", "openrouter", "llm7", "zai"):
        monkeypatch.setattr(tiers.settings, f"{provider}_api_keys", None)
    monkeypatch.setattr(tiers.settings, "llm7_enabled", False)
    monkeypatch.setattr(tiers.settings, "llm_interactive_chain", None)
    client = tiers.tier1_client()
    assert isinstance(client, GroqClient)
