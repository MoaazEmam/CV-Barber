import json
import time

from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.prompts import PARSER_SYSTEM_PROMPT, PARSER_USER_PROMPT_TEMPLATE
from app.schemas.master_cv import MasterCV


class CVParser:
    def __init__(self, client: BaseLLMClient | None = None):
        self._client = client or LLMClientFactory.create()

    def parse(self, raw_cv_text: str, max_retries: int = 3) -> MasterCV:
        user_prompt = PARSER_USER_PROMPT_TEMPLATE.format(cv_text=raw_cv_text)

        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                raw_response = self._client.complete_json(
                    PARSER_SYSTEM_PROMPT,
                    user_prompt
                )
                data = json.loads(raw_response)
                return MasterCV(**data)

            except json.JSONDecodeError as e:
                last_error = e
                print(f"[CVParser] Attempt {attempt}: invalid JSON — {e}")

            except Exception as e:
                last_error = e
                print(f"[CVParser] Attempt {attempt}: validation error — {e}")

                if "429" in str(e):
                    wait = 10 * attempt  # 10s, 20s, 30s
                    print(f"[CVParser] Rate limited — waiting {wait}s before retry")
                    time.sleep(wait)
                    continue

            time.sleep(2)

        raise RuntimeError(
            f"CVParser failed after {max_retries} attempts. "
            f"Last error: {last_error}"
        )