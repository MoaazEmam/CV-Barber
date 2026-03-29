import json
import time

from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.exceptions import (
    LLMRateLimitError,
    LLMAllKeysExhaustedError,
    LLMValidationError,
)
from app.llm.prompts import SCORER_SYSTEM_PROMPT, SCORER_USER_PROMPT_TEMPLATE
from app.schemas.config import TailoringConfig
from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV


class CVScorer:
    def __init__(self, client: BaseLLMClient | None = None):
        self._client = client or LLMClientFactory.create()

    def score(
        self,
        master_cv: MasterCV,
        job_description: str,
        config: TailoringConfig,
        max_retries: int = 3,
    ) -> TailoredCV:

        system_prompt = SCORER_SYSTEM_PROMPT.format(
            top_n_experience=config.top_n_experience,
            top_n_projects=config.top_n_projects,
        )

        user_prompt = SCORER_USER_PROMPT_TEMPLATE.format(
            job_title=config.job_title,
            company_name=config.company_name,
            job_description=job_description,
            master_cv_json=master_cv.model_dump_json(indent=2),
        )

        for attempt in range(1, max_retries + 1):
            try:
                raw_response = self._client.complete_json(system_prompt, user_prompt)
                data = json.loads(raw_response)
                return TailoredCV(**data)
            except (LLMRateLimitError, LLMAllKeysExhaustedError):
                raise
            except json.JSONDecodeError as e:
                print(f"[CVScorer] Attempt {attempt}: invalid JSON — {e}")
                time.sleep(2)
            except Exception as e:
                print(f"[CVScorer] Attempt {attempt}: validation error — {e}")
                time.sleep(2)
        raise LLMValidationError(f"Failed to score CV after {max_retries} attempts.")
