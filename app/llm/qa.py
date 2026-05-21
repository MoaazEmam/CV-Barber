import json

import structlog

from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory
from app.llm.exceptions import LLMValidationError
from app.llm.prompt_loader import load_prompt
from app.llm.retry import async_retry_llm
from app.schemas.qa import QAResponse
from app.schemas.tailored_cv import TailoredCV

logger = structlog.get_logger()


class CVQAResponder:
    def __init__(self, client: BaseLLMClient | None = None):
        self.client = client or LLMClientFactory.create()
        self._system = load_prompt("qa_system")
        self._user_template = load_prompt("qa_user")

    @async_retry_llm(max_retries=3)
    async def answer(self, tailored_cv: TailoredCV, questions: list[str]) -> QAResponse:
        await logger.ainfo("qa_start", question_count=len(questions))
        user_prompt = self._user_template.format(
            tailored_cv_json=tailored_cv.model_dump_json(indent=2),
            questions_json=json.dumps(questions, indent=2),
        )
        raw = await self.client.complete_json(self._system, user_prompt)
        try:
            data = json.loads(raw)
            result = QAResponse.model_validate(data)
        except Exception as e:
            raise LLMValidationError(f"QA response validation failed: {e}") from e
        await logger.ainfo("qa_complete", answer_count=len(result.answers))
        return result
