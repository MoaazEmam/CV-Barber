import json
from unittest.mock import AsyncMock, patch

import pytest

from app.llm.base_client import BaseLLMClient
from app.llm.exceptions import LLMValidationError
from app.pipeline.schema_extract import SchemaExtractor
from app.pipeline.spans import Span
from app.pipeline.structure import StructureIdentifier
from app.schemas.master_cv import MasterCV


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("app.llm.retry.asyncio.sleep", new=AsyncMock()):
        yield


class TestStructureIdentifier:
    async def test_returns_section_map_dict(self):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(
            {"name": "s0", "experience": [{"item_index": 0, "spans": ["s1", "s2"]}]}
        )
        ident = StructureIdentifier(client=client)
        result = await ident.identify([Span(id="s0", text="Jane")])
        assert result["name"] == "s0"
        assert result["experience"][0]["spans"] == ["s1", "s2"]

    async def test_spans_serialised_into_prompt(self):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = "{}"
        ident = StructureIdentifier(client=client)
        await ident.identify([Span(id="s0", text="Unique Span Text")])
        user_prompt = client.complete_json.call_args[0][1]
        assert "Unique Span Text" in user_prompt

    async def test_non_object_response_raises(self):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = "[1, 2, 3]"
        ident = StructureIdentifier(client=client)
        with pytest.raises(LLMValidationError):
            await ident.identify([Span(id="s0", text="x")])


class TestSchemaExtractor:
    async def test_returns_master_cv(self):
        client = AsyncMock(spec=BaseLLMClient)
        client.complete_json.return_value = json.dumps(
            {"full_name": "Jane Smith", "experience": [], "projects": [], "skills": []}
        )
        extractor = SchemaExtractor(client=client)
        result = await extractor.extract("raw cv text", section_map={})
        assert isinstance(result, MasterCV)
        assert result.full_name == "Jane Smith"
