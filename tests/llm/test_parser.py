import json
from unittest.mock import AsyncMock, patch

import pytest

from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import LLMValidationError
from app.llm.parser import CVParser
from app.schemas.master_cv import MasterCV


@pytest.fixture
def valid_master_cv_dict() -> dict:
    return {
        "full_name": "Moaaz Emam Ahmed",
        "email": "moaaz.emam06@eng-st.cu.edu.eg",
        "phone": "+20 1156637443",
        "github": "https://github.com/MoaazEmam",
        "education": [{
            "institution": "Cairo University",
            "degree": "B.Sc.",
            "field": "Communication and Computer Engineering",
            "date_range": {"start": "2022", "end": "2027"},
            "gpa": "3.58",
            "relevant_courses": []
        }],
        "experience": [{
            "title": "Data Engineering Intern",
            "company": "Instacodigo",
            "location": "Remote",
            "date_range": {"start": "Jul 2025", "end": "Oct 2025"},
            "bullets": ["Built ETL pipeline with Airflow"]
        }],
        "projects": [],
        "skills": [{"category": "Languages", "skills": ["Python", "C++"]}],
        "certifications": ["Backend Development Certificate – IEEE"]
    }


@pytest.fixture
def mock_client(valid_master_cv_dict) -> BaseLLMClient:
    client = AsyncMock(spec=BaseLLMClient)
    client.complete_json.return_value = json.dumps(valid_master_cv_dict)
    return client


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("app.llm.retry.asyncio.sleep", new=AsyncMock()):
        yield


class TestCVParser:
    async def test_returns_master_cv(self, mock_client):
        parser = CVParser(client=mock_client)
        result = await parser.parse("raw cv text")
        assert isinstance(result, MasterCV)
        assert result.full_name == "Moaaz Emam Ahmed"

    async def test_calls_complete_json_once(self, mock_client):
        parser = CVParser(client=mock_client)
        await parser.parse("raw cv text")
        assert mock_client.complete_json.call_count == 1

    async def test_cv_text_included_in_prompt(self, mock_client):
        parser = CVParser(client=mock_client)
        await parser.parse("this is my unique cv content")
        call_args = mock_client.complete_json.call_args
        user_prompt = call_args[0][1]
        assert "this is my unique cv content" in user_prompt

    async def test_retries_on_invalid_json(self, valid_master_cv_dict):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.side_effect = [
            "not valid json {{{{",
            "still not valid",
            json.dumps(valid_master_cv_dict),
        ]
        parser = CVParser(client=client)
        result = await parser.parse("raw cv text")
        assert result.full_name == "Moaaz Emam Ahmed"
        assert client.complete_json.call_count == 3

    async def test_raises_after_max_retries(self):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = "invalid json always"
        parser = CVParser(client=client)
        with pytest.raises(LLMValidationError):
            await parser.parse("raw cv text")
        assert client.complete_json.call_count == 3

    async def test_missing_required_field_triggers_retry(self):
        client = AsyncMock(spec=BaseLLMClient)
        # missing required 'full_name' field (email is intentionally optional now)
        client.complete_json.return_value = json.dumps({"email": "test@example.com"})
        parser = CVParser(client=client)
        with pytest.raises(LLMValidationError):
            await parser.parse("raw cv text")
        assert client.complete_json.call_count == 3
