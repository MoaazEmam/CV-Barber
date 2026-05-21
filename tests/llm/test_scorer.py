import json
from unittest.mock import AsyncMock, patch

import pytest

from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import LLMValidationError
from app.llm.scorer import CVScorer
from app.schemas.config import TailoringConfig
from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV


@pytest.fixture
def sample_master_cv() -> MasterCV:
    return MasterCV(
        full_name="Moaaz Emam Ahmed",
        email="moaaz@example.com",
        education=[],
        experience=[],
        projects=[],
        skills=[],
    )


@pytest.fixture
def sample_config() -> TailoringConfig:
    return TailoringConfig(
        job_title="Backend Engineering Intern",
        company_name="Acme Corp",
        top_n_experience=2,
        top_n_projects=3,
    )


@pytest.fixture
def valid_tailored_cv_dict() -> dict:
    return {
        "full_name": "Moaaz Emam Ahmed",
        "email": "moaaz@example.com",
        "job_title": "Backend Engineering Intern",
        "company_name": "Acme Corp",
        "tailored_summary": "Experienced backend developer targeting this role.",
        "experience": [],
        "projects": [],
        "skills": [],
        "education": [],
    }


@pytest.fixture
def mock_client(valid_tailored_cv_dict) -> BaseLLMClient:
    client = AsyncMock(spec=BaseLLMClient)
    client.complete_json.return_value = json.dumps(valid_tailored_cv_dict)
    return client


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("app.llm.retry.asyncio.sleep", new=AsyncMock()):
        yield


class TestCVScorer:
    async def test_returns_tailored_cv(self, mock_client, sample_master_cv, sample_config):
        scorer = CVScorer(client=mock_client)
        result = await scorer.score(sample_master_cv, "job description", sample_config)
        assert isinstance(result, TailoredCV)
        assert result.company_name == "Acme Corp"

    async def test_job_description_included_in_prompt(self, mock_client, sample_master_cv, sample_config):
        scorer = CVScorer(client=mock_client)
        await scorer.score(sample_master_cv, "unique job description text", sample_config)
        call_args = mock_client.complete_json.call_args
        user_prompt = call_args[0][1]
        assert "unique job description text" in user_prompt

    async def test_top_n_values_in_system_prompt(self, mock_client, sample_master_cv, sample_config):
        scorer = CVScorer(client=mock_client)
        await scorer.score(sample_master_cv, "job description", sample_config)
        call_args = mock_client.complete_json.call_args
        system_prompt = call_args[0][0]
        assert "2" in system_prompt   # top_n_experience
        assert "3" in system_prompt   # top_n_projects

    async def test_retries_on_invalid_json(self, sample_master_cv, sample_config, valid_tailored_cv_dict):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.side_effect = [
            "invalid json",
            json.dumps(valid_tailored_cv_dict),
        ]
        scorer = CVScorer(client=client)
        result = await scorer.score(sample_master_cv, "job description", sample_config)
        assert isinstance(result, TailoredCV)
        assert client.complete_json.call_count == 2

    async def test_raises_after_max_retries(self, sample_master_cv, sample_config):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = "always invalid"
        scorer = CVScorer(client=client)
        with pytest.raises(LLMValidationError):
            await scorer.score(sample_master_cv, "job description", sample_config)

    async def test_master_cv_serialized_into_prompt(self, mock_client, sample_master_cv, sample_config):
        scorer = CVScorer(client=mock_client)
        await scorer.score(sample_master_cv, "job description", sample_config)
        call_args = mock_client.complete_json.call_args
        user_prompt = call_args[0][1]
        assert "Moaaz Emam Ahmed" in user_prompt
