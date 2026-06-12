import json
from unittest.mock import AsyncMock, patch

import pytest

from app.llm.ats_scorer import ATSScorer
from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import LLMValidationError
from app.schemas.ats import GeneralATSScore, JobATSScore
from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV


@pytest.fixture
def sample_master_cv() -> MasterCV:
    return MasterCV(
        full_name="Moaaz Emam",
        email="m@x.com",
        education=[],
        experience=[],
        projects=[],
        skills=[],
    )


@pytest.fixture
def sample_tailored_cv() -> TailoredCV:
    return TailoredCV(
        full_name="Moaaz Emam",
        email="m@x.com",
        job_title="Backend Engineer",
        company_name="Acme",
        tailored_summary="A summary.",
        experience=[],
        projects=[],
        skills=[],
        education=[],
    )


@pytest.fixture
def valid_general() -> dict:
    return {
        "score": 82,
        "strengths": ["Clear structure", "Action verbs"],
        "improvements": ["Quantify results", "Add metrics", "Shorten summary"],
    }


@pytest.fixture
def valid_job() -> dict:
    return {
        "score": 67,
        "matched_keywords": ["python", "fastapi"],
        "missing_keywords": ["kubernetes"],
        "improvements": ["Mention k8s exposure", "Add system design bullet"],
    }


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("app.llm.retry.asyncio.sleep", new=AsyncMock()):
        yield


class TestATSScorerGeneral:
    async def test_returns_general_ats_score(self, valid_general, sample_master_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(valid_general)
        scorer = ATSScorer(client=client)
        result = await scorer.score_general(sample_master_cv)
        assert isinstance(result, GeneralATSScore)
        assert result.score == 82
        assert len(result.strengths) == 2
        assert len(result.improvements) == 3

    async def test_master_cv_serialized_into_prompt(self, valid_general, sample_master_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(valid_general)
        scorer = ATSScorer(client=client)
        await scorer.score_general(sample_master_cv)
        user_prompt = client.complete_json.call_args[0][1]
        assert "Moaaz Emam" in user_prompt

    async def test_general_retries_on_invalid_json(self, valid_general, sample_master_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.side_effect = ["garbage", json.dumps(valid_general)]
        scorer = ATSScorer(client=client)
        result = await scorer.score_general(sample_master_cv)
        assert result.score == 82
        assert client.complete_json.call_count == 2

    async def test_general_raises_after_max_retries(self, sample_master_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = "garbage"
        scorer = ATSScorer(client=client)
        with pytest.raises(LLMValidationError):
            await scorer.score_general(sample_master_cv)

    async def test_general_tolerates_missing_lists(self, sample_master_cv):
        client = AsyncMock(spec=BaseLLMClient)
        # Missing `improvements` is non-vital — coerced to [] rather than failing.
        client.complete_json.return_value = json.dumps(
            {"score": 50, "strengths": ["x"]}
        )
        scorer = ATSScorer(client=client)
        result = await scorer.score_general(sample_master_cv)
        assert result.score == 50
        assert result.improvements == []

    async def test_general_raises_on_missing_score(self, sample_master_cv):
        client = AsyncMock(spec=BaseLLMClient)
        # A scoreless ATS result is vital info missing — must still fail/retry.
        client.complete_json.return_value = json.dumps(
            {"strengths": ["x"], "improvements": ["y"]}
        )
        scorer = ATSScorer(client=client)
        with pytest.raises(LLMValidationError):
            await scorer.score_general(sample_master_cv)


class TestATSScorerJob:
    async def test_returns_job_ats_score(self, valid_job, sample_tailored_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(valid_job)
        scorer = ATSScorer(client=client)
        result = await scorer.score_job(sample_tailored_cv, "Build APIs in Python")
        assert isinstance(result, JobATSScore)
        assert result.score == 67
        assert "python" in result.matched_keywords
        assert "kubernetes" in result.missing_keywords

    async def test_job_description_in_prompt(self, valid_job, sample_tailored_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(valid_job)
        scorer = ATSScorer(client=client)
        await scorer.score_job(sample_tailored_cv, "very unique JD body")
        user_prompt = client.complete_json.call_args[0][1]
        assert "very unique JD body" in user_prompt

    async def test_tailored_cv_in_prompt(self, valid_job, sample_tailored_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(valid_job)
        scorer = ATSScorer(client=client)
        await scorer.score_job(sample_tailored_cv, "jd")
        user_prompt = client.complete_json.call_args[0][1]
        assert "Moaaz Emam" in user_prompt

    async def test_job_retries_on_invalid_json(self, valid_job, sample_tailored_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.side_effect = ["bad", json.dumps(valid_job)]
        scorer = ATSScorer(client=client)
        result = await scorer.score_job(sample_tailored_cv, "jd")
        assert result.score == 67
        assert client.complete_json.call_count == 2

    async def test_job_raises_after_max_retries(self, sample_tailored_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = "bad"
        scorer = ATSScorer(client=client)
        with pytest.raises(LLMValidationError):
            await scorer.score_job(sample_tailored_cv, "jd")

    async def test_long_jd_truncated(self, valid_job, sample_tailored_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(valid_job)
        scorer = ATSScorer(client=client)
        long_jd = "x" * 60_000 + "SENTINEL_TAIL"
        await scorer.score_job(sample_tailored_cv, long_jd)
        user_prompt = client.complete_json.call_args[0][1]
        assert "SENTINEL_TAIL" not in user_prompt
        assert "x" * 100 in user_prompt

    async def test_relevance_fields_excluded_from_prompt(self, valid_job):
        # The tailoring engine's internal scores must not be shown to the ATS
        # model (anchoring bias) — they're excluded from the serialized CV.
        cv = TailoredCV(
            full_name="Moaaz Emam",
            job_title="Backend Engineer",
            company_name="Acme",
            tailored_summary="A summary.",
            experience=[
                {
                    "title": "Engineer",
                    "company": "Acme",
                    "bullets": ["Built APIs"],
                    "relevance_score": 9,
                    "relevance_reason": "UNIQUE_REASON_MARKER",
                }
            ],
            projects=[],
            skills=[],
            education=[],
        )
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(valid_job)
        scorer = ATSScorer(client=client)
        await scorer.score_job(cv, "jd")
        user_prompt = client.complete_json.call_args[0][1]
        assert "relevance_score" not in user_prompt
        assert "UNIQUE_REASON_MARKER" not in user_prompt
        assert "Built APIs" in user_prompt

    async def test_keyword_lists_capped(self, sample_tailored_cv):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(
            {
                "score": 50,
                "matched_keywords": [f"m{i}" for i in range(30)],
                "missing_keywords": [f"k{i}" for i in range(20)],
                "improvements": ["x"],
            }
        )
        scorer = ATSScorer(client=client)
        result = await scorer.score_job(sample_tailored_cv, "jd")
        assert len(result.matched_keywords) == 15
        assert len(result.missing_keywords) == 6
        # Caps keep the head of the list (prompt orders most-important-first).
        assert result.missing_keywords[0] == "k0"
