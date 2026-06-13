"""Q&A targeted company-fact lookup orchestration (app.api.routes.qa)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.api.routes.qa as qa_route
from app.db.models import ApplicationModel, MasterCVModel
from app.schemas.qa import QAItem, QAResponse


async def _seed_application(db_session, user):
    cv = MasterCVModel(
        id=uuid.uuid4(), user_id=user.id, raw_file=b"x", file_type="pdf", parsed_data={}
    )
    db_session.add(cv)
    await db_session.commit()
    app_row = ApplicationModel(
        id=uuid.uuid4(),
        user_id=user.id,
        master_cv_id=cv.id,
        job_title="Backend Engineer",
        company_name="Acme",
        job_description="Build APIs.",
        tailored_cv_data={
            "full_name": "Moaaz Emam",
            "job_title": "Backend Engineer",
            "company_name": "Acme",
            "tailored_summary": "A summary.",
            "experience": [],
            "projects": [],
            "skills": [],
            "education": [],
        },
    )
    db_session.add(app_row)
    await db_session.commit()
    return app_row


def _responder_returning(*responses):
    """Patch CVQAResponder so .answer yields the given QAResponses in order."""
    responder = MagicMock()
    responder.answer = AsyncMock(side_effect=list(responses))
    return patch.object(qa_route, "CVQAResponder", return_value=responder), responder


def _resp(answer, lookup=None):
    return QAResponse(
        answers=[QAItem(question="What does Acme build?", answer=answer, company_lookup_query=lookup)]
    )


class TestQALookupOrchestration:
    async def test_no_lookup_single_pass(self, client, db_session, test_user, user_headers):
        app_row = await _seed_application(db_session, test_user)
        patcher, responder = _responder_returning(_resp("From the CV."))
        with patcher, patch.object(
            qa_route, "get_company_research", new=AsyncMock(return_value="base")
        ), patch.object(qa_route, "search_enabled", return_value=True), patch.object(
            qa_route, "lookup_and_append_company_facts", new=AsyncMock()
        ) as lookup:
            resp = await client.post(
                f"/api/applications/{app_row.id}/qa",
                json={"questions": ["What does Acme build?"]},
                headers=user_headers,
            )
        assert resp.status_code == 200
        assert responder.answer.call_count == 1
        lookup.assert_not_called()
        # Internal field never leaks to the client.
        assert "company_lookup_query" not in resp.text

    async def test_lookup_triggers_second_pass(self, client, db_session, test_user, user_headers):
        app_row = await _seed_application(db_session, test_user)
        patcher, responder = _responder_returning(
            _resp("Best guess.", lookup="Acme products"),
            _resp("Acme builds rockets, per research."),
        )
        with patcher, patch.object(
            qa_route, "get_company_research", new=AsyncMock(return_value="base")
        ), patch.object(qa_route, "search_enabled", return_value=True), patch.object(
            qa_route,
            "lookup_and_append_company_facts",
            new=AsyncMock(return_value="base\nAcme builds rockets"),
        ) as lookup:
            resp = await client.post(
                f"/api/applications/{app_row.id}/qa",
                json={"questions": ["What does Acme build?"]},
                headers=user_headers,
            )
        assert resp.status_code == 200
        assert responder.answer.call_count == 2
        lookup.assert_awaited_once()
        assert resp.json()["answers"][0]["answer"] == "Acme builds rockets, per research."

    async def test_lookup_skipped_when_search_disabled(
        self, client, db_session, test_user, user_headers
    ):
        app_row = await _seed_application(db_session, test_user)
        patcher, responder = _responder_returning(_resp("Best guess.", lookup="Acme products"))
        with patcher, patch.object(
            qa_route, "get_company_research", new=AsyncMock(return_value=None)
        ), patch.object(qa_route, "search_enabled", return_value=False), patch.object(
            qa_route, "lookup_and_append_company_facts", new=AsyncMock()
        ) as lookup:
            resp = await client.post(
                f"/api/applications/{app_row.id}/qa",
                json={"questions": ["What does Acme build?"]},
                headers=user_headers,
            )
        assert resp.status_code == 200
        assert responder.answer.call_count == 1
        lookup.assert_not_called()

    async def test_prose_hedge_triggers_fallback_search(
        self, client, db_session, test_user, user_headers
    ):
        # Model hedged in prose WITHOUT setting company_lookup_query — the
        # heuristic backstop should still trigger the search + second pass.
        app_row = await _seed_application(db_session, test_user)
        patcher, responder = _responder_returning(
            _resp("The CV does not specify what GSCS does; a company lookup might be necessary."),
            _resp("GSCS is Siemens' Global Sales & Customer Success org."),
        )
        with patcher, patch.object(
            qa_route, "get_company_research", new=AsyncMock(return_value="base")
        ), patch.object(qa_route, "search_enabled", return_value=True), patch.object(
            qa_route,
            "lookup_and_append_company_facts",
            new=AsyncMock(return_value="base\nGlobal Sales & Customer Success"),
        ) as lookup:
            resp = await client.post(
                f"/api/applications/{app_row.id}/qa",
                json={"questions": ["What does GSCS do?"]},
                headers=user_headers,
            )
        assert resp.status_code == 200
        assert responder.answer.call_count == 2
        lookup.assert_awaited_once()
        assert "Global Sales & Customer Success" in resp.json()["answers"][0]["answer"]

    async def test_no_second_pass_when_research_unchanged(
        self, client, db_session, test_user, user_headers
    ):
        app_row = await _seed_application(db_session, test_user)
        patcher, responder = _responder_returning(_resp("Best guess.", lookup="Acme products"))
        with patcher, patch.object(
            qa_route, "get_company_research", new=AsyncMock(return_value="base")
        ), patch.object(qa_route, "search_enabled", return_value=True), patch.object(
            qa_route,
            "lookup_and_append_company_facts",
            new=AsyncMock(return_value="base"),  # nothing new found
        ):
            resp = await client.post(
                f"/api/applications/{app_row.id}/qa",
                json={"questions": ["What does Acme build?"]},
                headers=user_headers,
            )
        assert resp.status_code == 200
        # Enriched research identical to original → no regeneration.
        assert responder.answer.call_count == 1
