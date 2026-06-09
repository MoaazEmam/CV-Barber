"""Tier client selection."""

from app.llm.groq_client import GroqClient
from app.pipeline import tiers


def test_tier1_client_is_groq_factory(monkeypatch):
    # client_factory reads the same settings singleton as tiers.
    monkeypatch.setattr(tiers.settings, "llm_provider", "groq")
    monkeypatch.setattr(tiers.settings, "groq_api_keys", "k1")
    monkeypatch.setattr(tiers.settings, "gemini_api_keys", "")
    monkeypatch.setattr(tiers.settings, "gemini_api_key", "def_key")
    client = tiers.tier1_client()
    assert isinstance(client, GroqClient)
