"""JD enrichment endpoints (app.api.routes.enrich)."""

from unittest.mock import AsyncMock, patch

import pytest

import app.api.routes.enrich as enrich_route
from app.config import settings
from app.services.search import SearchError


@pytest.fixture(autouse=True)
def _no_real_key(monkeypatch):
    # Never inherit a real Tavily key from the developer's .env in tests.
    monkeypatch.setattr(settings, "tavily_api_key", None)


class TestEnabledEndpoint:
    async def test_anonymous_401(self, client):
        resp = await client.get("/api/enrich-jd/enabled")
        assert resp.status_code == 401

    async def test_disabled_by_default(self, client, user_headers):
        resp = await client.get("/api/enrich-jd/enabled", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json() == {"enabled": False}

    async def test_enabled_with_key(self, client, user_headers, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "tavily_api_key", "tvly-test")
        resp = await client.get("/api/enrich-jd/enabled", headers=user_headers)
        assert resp.json() == {"enabled": True}


class TestEnrichEndpoint:
    async def test_404_when_disabled(self, client, user_headers):
        resp = await client.post(
            "/api/enrich-jd", json={"job_title": "Backend Engineer"}, headers=user_headers
        )
        assert resp.status_code == 404

    async def test_returns_supplement_and_sources(self, client, user_headers, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "tavily_api_key", "tvly-test")
        with patch.object(
            enrich_route,
            "enrich_job_description",
            new=AsyncMock(
                return_value=("Typical duties...", [{"title": "src", "url": "https://x.test"}])
            ),
        ):
            resp = await client.post(
                "/api/enrich-jd",
                json={"job_title": "Backend Engineer", "company_name": "Acme"},
                headers=user_headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["supplement"] == "Typical duties..."
        assert body["sources"][0]["url"] == "https://x.test"

    async def test_search_failure_502(self, client, user_headers, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "tavily_api_key", "tvly-test")
        with patch.object(
            enrich_route,
            "enrich_job_description",
            new=AsyncMock(side_effect=SearchError("down")),
        ):
            resp = await client.post(
                "/api/enrich-jd", json={"job_title": "Backend Engineer"}, headers=user_headers
            )
        assert resp.status_code == 502
