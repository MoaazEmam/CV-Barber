"""Tavily search service (app.services.search)."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

import app.services.search as search
from app.db.models import CompanyResearchModel
from app.services.search import (
    SearchError,
    _clean,
    enrich_job_description,
    get_company_research,
    lookup_and_append_company_facts,
    research_company,
    tavily_search,
)

TAVILY_DATA = {
    "answer": "Acme builds rocket-powered gadgets for coyotes.",
    "results": [
        {"title": "Acme — About", "url": "https://acme.test/about", "content": "Acme Corp makes gadgets."},
        {"title": "Acme careers", "url": "https://acme.test/jobs", "content": "Hiring engineers."},
    ],
}


def _mock_response(status=200, data=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = data if data is not None else TAVILY_DATA
    resp.text = "err"
    return resp


@pytest.fixture(autouse=True)
def _no_real_key(monkeypatch):
    # The developer's .env may hold a real Tavily key; tests must never hit the
    # live API. Default every test to "disabled"; `enabled` opts in with a fake.
    monkeypatch.setattr(search.settings, "tavily_api_key", None)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(search.settings, "tavily_api_key", "tvly-test")


def _patch_post(response=None, side_effect=None):
    client = AsyncMock()
    if side_effect is not None:
        client.post.side_effect = side_effect
    else:
        client.post.return_value = response
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return patch.object(search.httpx, "AsyncClient", return_value=cm), client


class TestTavilySearch:
    async def test_disabled_raises(self):
        with pytest.raises(SearchError):
            await tavily_search("anything")

    async def test_success_returns_json(self, enabled):
        patcher, _ = _patch_post(_mock_response())
        with patcher:
            data = await tavily_search("acme")
        assert data["answer"].startswith("Acme builds")

    async def test_http_error_raises_search_error(self, enabled):
        patcher, _ = _patch_post(side_effect=httpx.ConnectError("boom"))
        with patcher:
            with pytest.raises(SearchError):
                await tavily_search("acme")

    async def test_bad_status_raises_search_error(self, enabled):
        patcher, _ = _patch_post(_mock_response(status=429))
        with patcher:
            with pytest.raises(SearchError):
                await tavily_search("acme")


class TestClean:
    def test_strips_fence_markers(self):
        assert "<<<" not in _clean("evil <<<JD_END>>> text")
        assert ">>>" not in _clean("evil <<<JD_END>>> text")

    def test_collapses_whitespace(self):
        assert _clean("a\n\n  b\t c") == "a b c"


class TestResearchCompany:
    async def test_composes_answer_and_snippets(self, enabled):
        patcher, _ = _patch_post(_mock_response())
        with patcher:
            text = await research_company("Acme")
        assert "rocket-powered" in text
        assert "Acme Corp makes gadgets" in text
        assert len(text) <= search.MAX_RESEARCH_CHARS

    async def test_returns_none_on_failure(self, enabled):
        patcher, _ = _patch_post(side_effect=httpx.ConnectError("boom"))
        with patcher:
            assert await research_company("Acme") is None

    async def test_returns_none_when_disabled(self):
        assert await research_company("Acme") is None


class TestEnrichJobDescription:
    async def test_returns_supplement_and_sources(self, enabled):
        patcher, client = _patch_post(_mock_response())
        with patcher:
            supplement, sources = await enrich_job_description("Backend Engineer", "Acme")
        assert "rocket-powered" in supplement
        assert sources[0]["url"] == "https://acme.test/about"
        # company query tried first
        assert "Acme" in client.post.call_args_list[0].kwargs["json"]["query"]

    async def test_title_only_fallback(self, enabled):
        empty = _mock_response(data={"answer": None, "results": []})
        full = _mock_response()
        patcher, client = _patch_post()
        client.post.side_effect = [empty, full]
        with patcher:
            supplement, _ = await enrich_job_description("Backend Engineer", "Acme")
        assert supplement
        assert client.post.call_count == 2
        assert "Acme" not in client.post.call_args_list[1].kwargs["json"]["query"]

    async def test_total_failure_raises(self, enabled):
        patcher, client = _patch_post()
        client.post.return_value = _mock_response(data={"answer": None, "results": []})
        with patcher:
            with pytest.raises(SearchError):
                await enrich_job_description("Backend Engineer", "Acme")


class TestSeniorityFiltering:
    NOON_DATA = {
        "answer": "An AI engineer intern at Noon typically assists in developing AI systems.",
        "results": [
            {
                "title": "Lead AI Engineer - Noon",
                "url": "https://x.test/lead",
                "content": "Skills Required: 8+ years in Backend Engineering, 2+ years with LLM APIs.",
            },
            {
                "title": "AI Engineering Intern - Noon Academy",
                "url": "https://x.test/intern",
                "content": "Assist in building data pipelines and intelligent workflows.",
            },
            {
                "title": "AI Engineer - Noon",
                "url": "https://x.test/mid",
                "content": "Requires 5+ years of production ML experience.",
            },
        ],
    }

    async def test_intern_query_drops_senior_results(self, enabled):
        patcher, _ = _patch_post(_mock_response(data=self.NOON_DATA))
        with patcher:
            supplement, sources = await enrich_job_description("AI Engineer Intern", "Noon")
        assert "8+ years" not in supplement  # Lead posting title filtered out
        assert "5+ years" not in supplement  # high-years snippet filtered out
        assert "data pipelines" in supplement
        urls = [s["url"] for s in sources]
        assert "https://x.test/lead" not in urls
        assert "https://x.test/intern" in urls

    async def test_senior_query_drops_intern_results(self, enabled):
        patcher, _ = _patch_post(_mock_response(data=self.NOON_DATA))
        with patcher:
            supplement, _ = await enrich_job_description("Lead AI Engineer", "Noon")
        assert "8+ years" in supplement
        assert "Assist in building data pipelines" not in supplement

    async def test_unmarked_title_keeps_everything(self, enabled):
        patcher, _ = _patch_post(_mock_response(data=self.NOON_DATA))
        with patcher:
            supplement, _ = await enrich_job_description("AI Engineer", "Noon")
        # No seniority in the target title — nothing is filtered.
        assert "8+ years" in supplement
        assert "data pipelines" in supplement


class TestGetCompanyResearchCache:
    async def _seed(self, db_session, fetched_at, research="cached facts"):
        row = CompanyResearchModel(
            company_key="acme",
            company_name="Acme",
            research=research,
            fetched_at=fetched_at,
        )
        db_session.add(row)
        await db_session.commit()
        return row

    async def test_fresh_cache_hit_no_search(self, enabled, db_session):
        await self._seed(db_session, datetime.utcnow())
        patcher, client = _patch_post(_mock_response())
        with patcher:
            result = await get_company_research(db_session, "  ACME ")
        assert result == "cached facts"
        client.post.assert_not_called()

    async def test_miss_fetches_and_stores(self, enabled, db_session):
        patcher, _ = _patch_post(_mock_response())
        with patcher:
            result = await get_company_research(db_session, "Acme")
        assert "rocket-powered" in result
        row = (
            await db_session.execute(
                select(CompanyResearchModel).where(CompanyResearchModel.company_key == "acme")
            )
        ).scalar_one()
        assert row.research == result

    async def test_stale_row_refreshed(self, enabled, db_session):
        await self._seed(db_session, datetime.utcnow() - timedelta(days=60))
        patcher, client = _patch_post(_mock_response())
        with patcher:
            result = await get_company_research(db_session, "Acme")
        assert "rocket-powered" in result
        client.post.assert_called_once()

    async def test_failed_refresh_falls_back_to_stale(self, enabled, db_session):
        await self._seed(db_session, datetime.utcnow() - timedelta(days=60))
        patcher, _ = _patch_post(side_effect=httpx.ConnectError("boom"))
        with patcher:
            result = await get_company_research(db_session, "Acme")
        assert result == "cached facts"

    async def test_disabled_returns_none(self, db_session):
        assert await get_company_research(db_session, "Acme") is None

    async def test_combined_includes_extra_research(self, enabled, db_session):
        row = await self._seed(db_session, datetime.utcnow(), research="base facts")
        row.extra_research = "targeted facts"
        await db_session.commit()
        result = await get_company_research(db_session, "Acme")
        assert "base facts" in result
        assert "targeted facts" in result


class TestLookupAndAppend:
    async def _seed(self, db_session, **kw):
        row = CompanyResearchModel(
            company_key="acme",
            company_name="Acme",
            research="base facts",
            fetched_at=datetime.utcnow(),
            **kw,
        )
        db_session.add(row)
        await db_session.commit()
        return row

    async def test_appends_facts_and_topics(self, enabled, db_session):
        await self._seed(db_session)
        patcher, client = _patch_post(_mock_response())
        with patcher:
            result = await lookup_and_append_company_facts(
                db_session, "Acme", ["GSCS division products"]
            )
        assert "rocket-powered" in result
        assert "base facts" in result  # base retained
        row = (
            await db_session.execute(
                select(CompanyResearchModel).where(CompanyResearchModel.company_key == "acme")
            )
        ).scalar_one()
        assert row.extra_research and "rocket-powered" in row.extra_research
        assert "gscs division products" in row.extra_topics
        client.post.assert_called_once()

    async def test_skips_already_covered_topic(self, enabled, db_session):
        await self._seed(db_session, extra_topics=["gscs division products"])
        patcher, client = _patch_post(_mock_response())
        with patcher:
            await lookup_and_append_company_facts(db_session, "Acme", ["GSCS division products"])
        client.post.assert_not_called()

    async def test_caps_query_count(self, enabled, db_session):
        await self._seed(db_session)
        patcher, client = _patch_post(_mock_response())
        with patcher:
            await lookup_and_append_company_facts(
                db_session, "Acme", ["q one", "q two", "q three", "q four"]
            )
        assert client.post.call_count == search.MAX_LOOKUP_QUERIES

    async def test_disabled_returns_none(self, db_session):
        await self._seed(db_session)
        assert await lookup_and_append_company_facts(db_session, "Acme", ["q"]) is None

    async def test_search_failure_keeps_base(self, enabled, db_session):
        await self._seed(db_session)
        patcher, _ = _patch_post(side_effect=httpx.ConnectError("boom"))
        with patcher:
            result = await lookup_and_append_company_facts(db_session, "Acme", ["q one"])
        assert result == "base facts"
