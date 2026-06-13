"""Optional company-research / JD context blocks in cover-letter and QA prompts,
and the JD-supplement composition helper."""

import json
from unittest.mock import AsyncMock

from app.llm.base_client import BaseLLMClient
from app.llm.cover_letter import CoverLetterGenerator
from app.llm.qa import CVQAResponder
from app.llm.scorer import compose_jd
from app.schemas.tailored_cv import TailoredCV


def _cv() -> TailoredCV:
    return TailoredCV(
        full_name="Moaaz Emam",
        job_title="Backend Engineer",
        company_name="Acme",
        tailored_summary="A summary.",
        experience=[],
        projects=[],
        skills=[],
        education=[],
    )


class TestComposeJd:
    def test_no_supplement_returns_jd_unchanged(self):
        assert compose_jd("plain jd", None) == "plain jd"
        assert compose_jd("plain jd", "   ") == "plain jd"

    def test_supplement_is_fenced(self):
        out = compose_jd("plain jd", "extra duties")
        assert out.startswith("plain jd")
        assert "<<<JD_SUPPLEMENT_START>>>" in out
        assert "extra duties" in out
        assert "<<<JD_SUPPLEMENT_END>>>" in out


class TestCoverLetterResearchBlock:
    async def test_research_included_when_present(self):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete.return_value = "Dear team..."
        gen = CoverLetterGenerator(client=client)
        await gen.generate(_cv(), "jd", company_research="Acme ships rockets")
        prompt = client.complete.call_args[0][1]
        assert "<<<COMPANY_RESEARCH_START>>>" in prompt
        assert "Acme ships rockets" in prompt

    async def test_block_absent_when_no_research(self):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete.return_value = "Dear team..."
        gen = CoverLetterGenerator(client=client)
        await gen.generate(_cv(), "jd")
        prompt = client.complete.call_args[0][1]
        assert "COMPANY_RESEARCH" not in prompt


class TestQAContextBlocks:
    def _client(self):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(
            {"answers": [{"question": "q", "answer": "a"}]}
        )
        return client

    async def test_jd_and_research_included(self):
        client = self._client()
        responder = CVQAResponder(client=client)
        await responder.answer(
            _cv(), ["Why Acme?"], job_description="build apis", company_research="Acme facts"
        )
        prompt = client.complete_json.call_args[0][1]
        assert "<<<JOB_DESCRIPTION_START>>>" in prompt
        assert "build apis" in prompt
        assert "<<<COMPANY_RESEARCH_START>>>" in prompt
        assert "Acme facts" in prompt

    async def test_blocks_absent_by_default(self):
        client = self._client()
        responder = CVQAResponder(client=client)
        await responder.answer(_cv(), ["Why Acme?"])
        prompt = client.complete_json.call_args[0][1]
        assert "JOB_DESCRIPTION_START" not in prompt
        assert "COMPANY_RESEARCH" not in prompt
