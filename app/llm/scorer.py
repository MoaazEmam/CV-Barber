import json
import time

from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.prompts import SCORER_SYSTEM_PROMPT, SCORER_USER_PROMPT_TEMPLATE
from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV
from app.schemas.config import TailoringConfig


class CVScorer:
    def __init__(self, client: BaseLLMClient | None = None):
        self._client = client or LLMClientFactory.create()

    def score(
        self,
        master_cv: MasterCV,
        job_description: str,
        config: TailoringConfig,
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

        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                raw_response = self._client.complete_json(
                    system_prompt,
                    user_prompt
                )
                data = json.loads(raw_response)
                return TailoredCV(**data)

            except json.JSONDecodeError as e:
                last_error = e
                print(f"[CVScorer] Attempt {attempt}: invalid JSON — {e}")

            except Exception as e:
                last_error = e
                print(f"[CVScorer] Attempt {attempt}: validation error — {e}")

                if "429" in str(e):
                    wait = 10 * attempt  # 10s, 20s, 30s
                    print(f"[CVParser] Rate limited — waiting {wait}s before retry")
                    time.sleep(wait)
                    continue

            time.sleep(2)

        raise RuntimeError(
            f"CVScorer failed after 3 attempts. "
            f"Last error: {last_error}"
        )