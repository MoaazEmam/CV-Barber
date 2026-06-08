"""Structure identification (Tier 1).

Labels the normalised spans of a CV with semantic roles and groups them into
sections/entries, producing a ``section_map``. This is a one-time call per unique
CV, cached against the dedup hash. The map is format-agnostic: both the PDF and
DOCX paths normalise to :class:`~app.pipeline.spans.Span` before calling here.
"""

from __future__ import annotations

import json

import structlog

from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import (
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)
from app.llm.prompt_loader import load_prompt
from app.llm.retry import async_retry_llm
from app.pipeline.spans import Span
from app.pipeline.tiers import tier1_client

log = structlog.get_logger()


class StructureIdentifier:
    def __init__(self, client: BaseLLMClient | None = None):
        self._client = client or tier1_client()
        self._system = load_prompt("structure_system")
        self._user_template = load_prompt("structure_user")

    @async_retry_llm(max_retries=3)
    async def identify(self, spans: list[Span]) -> dict:
        spans_json = json.dumps([s.to_prompt_dict() for s in spans], ensure_ascii=False)
        user_prompt = self._user_template.format(spans_json=spans_json)
        try:
            raw = await self._client.complete_json(self._system, user_prompt)
            section_map = json.loads(raw)
            if not isinstance(section_map, dict):
                raise LLMValidationError("Section map must be a JSON object.")
            return section_map
        except (LLMRateLimitError, LLMAllKeysExhaustedError):
            raise
        except json.JSONDecodeError as e:
            raise LLMValidationError(f"Invalid JSON from structure LLM: {e}") from e
        except LLMValidationError:
            raise
        except Exception as e:
            raise LLMValidationError(f"Failed to build section map: {e}") from e
