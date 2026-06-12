"""LLM tier selection.

Both tiers run on the interactive fallback chain (Groq-first; see
app/llm/client_factory.py for the provider order) — parsing and tailoring are
user-facing, latency-sensitive requests.
"""

from __future__ import annotations

from app.config import settings  # noqa: F401  (re-exported for tests/monkeypatching)
from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory


def tier1_client() -> BaseLLMClient:
    """Tier 1 text client (structure ID, schema extraction) — interactive chain."""
    return LLMClientFactory.create("interactive")


def tier2_client() -> BaseLLMClient:
    """Tier 2 client (tailoring, rewriting) — interactive chain."""
    return LLMClientFactory.create("interactive")
