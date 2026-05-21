import json

from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.exceptions import (
    LLMAllKeysExhaustedError,
    LLMRateLimitError,
    LLMValidationError,
)
from app.llm.prompt_loader import load_prompt
from app.llm.retry import async_retry_llm
from app.schemas.master_cv import MasterCV


class CVParser:
    def __init__(self, client: BaseLLMClient | None = None):
        self._client = client or LLMClientFactory.create()
        self._system = load_prompt("parser_system")
        self._user_template = load_prompt("parser_user")

    @async_retry_llm(max_retries=3)
    async def parse(self, raw_cv_text: str) -> MasterCV:
        user_prompt = self._user_template.format(cv_text=raw_cv_text)
        try:
            raw_response = await self._client.complete_json(
                self._system, user_prompt
            )
            data = json.loads(raw_response)
            return MasterCV(**data)
        except (LLMRateLimitError, LLMAllKeysExhaustedError):
            raise
        except json.JSONDecodeError as e:
            raise LLMValidationError(f"Invalid JSON from LLM: {e}") from e
        except Exception as e:
            raise LLMValidationError(f"Failed to validate parsed CV: {e}") from e
