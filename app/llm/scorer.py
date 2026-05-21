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
from app.schemas.config import TailoringConfig
from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV


class CVScorer:
    def __init__(self, client: BaseLLMClient | None = None):
        self._client = client or LLMClientFactory.create()
        self._system_template = load_prompt("scorer_system")
        self._user_template = load_prompt("scorer_user")

    @async_retry_llm(max_retries=3)
    async def score(
        self,
        master_cv: MasterCV,
        job_description: str,
        config: TailoringConfig,
    ) -> TailoredCV:

        system_prompt = self._system_template.format(
            top_n_experience=config.top_n_experience,
            top_n_projects=config.top_n_projects,
        )

        user_prompt = self._user_template.format(
            job_title=config.job_title,
            company_name=config.company_name,
            job_description=job_description,
            master_cv_json=master_cv.model_dump_json(indent=2),
        )

        try:
            raw_response = await self._client.complete_json(system_prompt, user_prompt)
            data = json.loads(raw_response)
            return TailoredCV(**data)
        except (LLMRateLimitError, LLMAllKeysExhaustedError):
            raise
        except json.JSONDecodeError as e:
            raise LLMValidationError(f"Invalid JSON from LLM: {e}") from e
        except Exception as e:
            raise LLMValidationError(f"Failed to validate tailored CV: {e}") from e
