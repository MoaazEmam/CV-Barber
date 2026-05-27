import structlog

from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.exceptions import LLMValidationError
from app.llm.prompt_loader import load_prompt
from app.llm.retry import async_retry_llm
from app.schemas.tailored_cv import TailoredCV

logger = structlog.get_logger()


class CoverLetterGenerator:
    def __init__(self, client: BaseLLMClient | None = None):
        self.client = client or LLMClientFactory.create()
        self._system = load_prompt("cover_letter_system")
        self._user_template = load_prompt("cover_letter_user")

    @async_retry_llm(max_retries=3)
    async def generate(self, tailored_cv: TailoredCV, job_description: str) -> str:
        await logger.ainfo("cover_letter_start")
        user_prompt = self._user_template.format(
            tailored_cv_json=tailored_cv.model_dump_json(indent=2),
            job_description=job_description,
        )
        result = await self.client.complete(self._system, user_prompt)
        if not result or not result.strip():
            raise LLMValidationError("Cover letter generation returned an empty response")
        await logger.ainfo("cover_letter_complete", chars=len(result))
        return result.strip()
