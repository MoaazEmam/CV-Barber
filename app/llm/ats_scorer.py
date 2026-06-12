import json

import structlog

from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.exceptions import LLMValidationError
from app.llm.prompt_loader import load_prompt
from app.llm.retry import async_retry_llm
from app.llm.scorer import MAX_JD_CHARS
from app.schemas.ats import GeneralATSScore, JobATSScore
from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV

logger = structlog.get_logger()


class ATSScorer:
    def __init__(self, client: BaseLLMClient | None = None):
        self.client = client or LLMClientFactory.create()
        self._general_system = load_prompt("ats_general_system")
        self._general_user_template = load_prompt("ats_general_user")
        self._job_system = load_prompt("ats_job_system")
        self._job_user_template = load_prompt("ats_job_user")

    @async_retry_llm(max_retries=3)
    async def score_general(self, master_cv: MasterCV) -> GeneralATSScore:
        await logger.ainfo("ats_general_start")
        user_prompt = self._general_user_template.format(
            master_cv_json=master_cv.model_dump_json(indent=2)
        )
        raw = await self.client.complete_json(self._general_system, user_prompt)
        try:
            result = GeneralATSScore.model_validate(json.loads(raw))
        except Exception as e:
            raise LLMValidationError(f"General ATS response validation failed: {e}") from e
        await logger.ainfo("ats_general_complete", score=result.score)
        return result

    @async_retry_llm(max_retries=3)
    async def score_job(self, tailored_cv: TailoredCV, job_description: str) -> JobATSScore:
        await logger.ainfo("ats_job_start")
        if len(job_description) > MAX_JD_CHARS:
            await logger.awarning(
                "ats_job_jd_truncated",
                original_chars=len(job_description),
                kept_chars=MAX_JD_CHARS,
            )
        # The tailoring engine's internal relevance fields are excluded so the
        # ATS model scores the CV content itself, not the earlier model's own
        # opinion of it (anchoring bias).
        tailored_cv_json = tailored_cv.model_dump_json(
            indent=2,
            exclude={
                "experience": {"__all__": {"relevance_score", "relevance_reason"}},
                "projects": {"__all__": {"relevance_score", "relevance_reason"}},
            },
        )
        user_prompt = self._job_user_template.format(
            job_description=job_description[:MAX_JD_CHARS],
            tailored_cv_json=tailored_cv_json,
        )
        raw = await self.client.complete_json(self._job_system, user_prompt)
        try:
            result = JobATSScore.model_validate(json.loads(raw))
        except Exception as e:
            raise LLMValidationError(f"Job ATS response validation failed: {e}") from e
        await logger.ainfo("ats_job_complete", score=result.score)
        return result
