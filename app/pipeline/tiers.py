"""LLM tier selection.

Tier 1 (structure ID, schema extraction): runs on the reliable Groq primary (with
Gemini fallback) via the existing factory — the same provider the proven legacy
parser used.

Tier 2 (tailoring, rewriting): the existing Groq->Gemini fallback chain.
"""

from __future__ import annotations

from app.config import settings  # noqa: F401  (re-exported for tests/monkeypatching)
from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory


def tier1_client() -> BaseLLMClient:
    """Tier 1 text client — Groq primary + Gemini fallback (reliable, big quota)."""
    return LLMClientFactory.create()


def tier2_client() -> BaseLLMClient:
    """Tier 2 client — existing provider selection + fallback chain."""
    return LLMClientFactory.create()
