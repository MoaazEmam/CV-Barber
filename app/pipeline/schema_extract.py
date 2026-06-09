"""Schema extraction (Tier 1).

Extracts the structured :class:`MasterCV` content from a CV. Reuses the proven
parser prompts (``parser_system``/``parser_user``) — the new pipeline's value is
the format-preserving *template*, not a different content schema, so the schema
step is intentionally the same well-tested extraction. One-time per unique CV,
cached against the dedup hash.
"""

from __future__ import annotations

import json

import structlog
from pydantic import ValidationError

from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import (
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)
from app.llm.prompt_loader import load_prompt
from app.llm.retry import async_retry_llm
from app.pipeline.tiers import tier1_client
from app.schemas.master_cv import MasterCV

log = structlog.get_logger()

# Safety net only — caps token spend / injection surface.
MAX_CV_CHARS = 50_000


class SchemaExtractor:
    def __init__(self, client: BaseLLMClient | None = None):
        self._client = client or tier1_client()
        self._system = load_prompt("parser_system")
        self._user_template = load_prompt("parser_user")

    @async_retry_llm(max_retries=3)
    async def extract(self, raw_text: str, section_map: dict | None = None) -> MasterCV:
        if len(raw_text) > MAX_CV_CHARS:
            log.warning(
                "schema_text_truncated",
                original_chars=len(raw_text),
                kept_chars=MAX_CV_CHARS,
            )
        user_prompt = self._user_template.format(cv_text=raw_text[:MAX_CV_CHARS])
        try:
            raw = await self._client.complete_json(self._system, user_prompt)
            data = json.loads(raw)
            return self._validate(data)
        except (LLMRateLimitError, LLMAllKeysExhaustedError):
            raise
        except json.JSONDecodeError as e:
            raise LLMValidationError(f"Invalid JSON from schema LLM: {e}") from e
        except Exception as e:
            raise LLMValidationError(f"Failed to validate extracted CV: {e}") from e

    @staticmethod
    def _validate(data: dict) -> MasterCV:
        """Validate the extracted CV. If only the best-effort ``additional_sections``
        is malformed, drop it and keep the core CV rather than failing the parse."""
        try:
            return MasterCV(**data)
        except ValidationError as ve:
            if any((err.get("loc") or [None])[0] == "additional_sections" for err in ve.errors()):
                log.warning("additional_sections_dropped_on_validation", error=str(ve)[:200])
                cleaned = {k: v for k, v in data.items() if k != "additional_sections"}
                return MasterCV(**cleaned)
            raise
