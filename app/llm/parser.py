import json
import time

from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.exceptions import (
    LLMRateLimitError,
    LLMAllKeysExhaustedError,
    LLMValidationError,
)
from app.llm.prompts import PARSER_SYSTEM_PROMPT, PARSER_USER_PROMPT_TEMPLATE
from app.schemas.master_cv import MasterCV


class CVParser:
    def __init__(self, client: BaseLLMClient | None = None):
        self._client = client or LLMClientFactory.create()

    def parse(self, raw_cv_text: str, max_retries: int = 3) -> MasterCV:
        user_prompt = PARSER_USER_PROMPT_TEMPLATE.format(cv_text=raw_cv_text)

        for attempt in range(1, max_retries + 1):
            try:
                raw_response = self._client.complete_json(
                    PARSER_SYSTEM_PROMPT, user_prompt
                )
                data = json.loads(raw_response)
                return MasterCV(**data)
            except (LLMRateLimitError, LLMAllKeysExhaustedError):
                raise
            except json.JSONDecodeError as e:
                print(f"[CVParser] Attempt {attempt}: invalid JSON — {e}")
                time.sleep(2)

            except Exception as e:
                print(f"[CVParser] Attempt {attempt}: validation error — {e}")
                time.sleep(2)
        raise LLMValidationError(f"Failed to parse CV after {max_retries} attempts.")
