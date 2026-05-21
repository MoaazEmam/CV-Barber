import json
from unittest.mock import AsyncMock, patch

import pytest

from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import LLMValidationError
from app.llm.qa import CVQAResponder
from app.schemas.qa import QAResponse
from app.schemas.tailored_cv import TailoredCV


@pytest.fixture
def sample_tailored_cv() -> TailoredCV:
    return TailoredCV(
        full_name="Moaaz Emam",
        email="moaaz@example.com",
        job_title="Backend Engineer",
        company_name="Acme",
        tailored_summary="A summary.",
        experience=[],
        projects=[],
        skills=[],
        education=[],
    )


@pytest.fixture
def valid_qa_response_dict() -> dict:
    return {
        "answers": [
            {"question": "Why do you want this job?", "answer": "Because reasons."},
            {"question": "Tell us a strength.", "answer": "I am curious."},
        ]
    }


@pytest.fixture
def mock_client(valid_qa_response_dict) -> BaseLLMClient:
    client = AsyncMock(spec=BaseLLMClient)
    client.complete_json.return_value = json.dumps(valid_qa_response_dict)
    return client


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("app.llm.retry.asyncio.sleep", new=AsyncMock()):
        yield


class TestCVQAResponder:
    async def test_returns_qa_response(self, mock_client, sample_tailored_cv):
        responder = CVQAResponder(client=mock_client)
        result = await responder.answer(
            sample_tailored_cv, ["Why do you want this job?", "Tell us a strength."]
        )
        assert isinstance(result, QAResponse)
        assert len(result.answers) == 2
        assert result.answers[0].answer == "Because reasons."

    async def test_questions_serialized_into_prompt(self, mock_client, sample_tailored_cv):
        responder = CVQAResponder(client=mock_client)
        await responder.answer(sample_tailored_cv, ["very unique question text"])
        user_prompt = mock_client.complete_json.call_args[0][1]
        assert "very unique question text" in user_prompt

    async def test_tailored_cv_serialized_into_prompt(self, mock_client, sample_tailored_cv):
        responder = CVQAResponder(client=mock_client)
        await responder.answer(sample_tailored_cv, ["q1"])
        user_prompt = mock_client.complete_json.call_args[0][1]
        assert "Moaaz Emam" in user_prompt

    async def test_retries_on_invalid_json(self, sample_tailored_cv, valid_qa_response_dict):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.side_effect = [
            "not json at all",
            json.dumps(valid_qa_response_dict),
        ]
        responder = CVQAResponder(client=client)
        result = await responder.answer(sample_tailored_cv, ["q1"])
        assert isinstance(result, QAResponse)
        assert client.complete_json.call_count == 2

    async def test_raises_after_max_retries(self, sample_tailored_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = "always invalid"
        responder = CVQAResponder(client=client)
        with pytest.raises(LLMValidationError):
            await responder.answer(sample_tailored_cv, ["q1"])

    async def test_raises_on_schema_mismatch(self, sample_tailored_cv):
        client = AsyncMock(spec=BaseLLMClient)
        # Valid JSON but wrong shape — no "answers" key.
        client.complete_json.return_value = json.dumps({"wrong_key": []})
        responder = CVQAResponder(client=client)
        with pytest.raises(LLMValidationError):
            await responder.answer(sample_tailored_cv, ["q1"])
