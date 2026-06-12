"""User feedback submission endpoints (app.api.routes.feedback)."""

import uuid

from sqlalchemy import select

from app.db.models import FeedbackModel


class TestSubmitFeedback:
    async def test_anonymous_401(self, client):
        resp = await client.post("/api/feedback", json={"type": "bug", "message": "broken"})
        assert resp.status_code == 401

    async def test_creates_row(self, client, db_session, test_user, user_headers):
        resp = await client.post(
            "/api/feedback",
            json={"type": "suggestion", "message": "Add dark mode", "page_context": "/tailor"},
            headers=user_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["type"] == "suggestion"
        assert body["status"] == "open"
        row = (await db_session.execute(select(FeedbackModel))).scalars().one()
        assert row.user_id == test_user.id
        assert row.message == "Add dark mode"
        assert row.page_context == "/tailor"

    async def test_bad_type_422(self, client, user_headers):
        resp = await client.post(
            "/api/feedback",
            json={"type": "rant", "message": "everything is bad"},
            headers=user_headers,
        )
        assert resp.status_code == 422

    async def test_short_message_422(self, client, user_headers):
        resp = await client.post(
            "/api/feedback",
            json={"type": "bug", "message": "ab"},
            headers=user_headers,
        )
        assert resp.status_code == 422


class TestListOwnFeedback:
    async def test_only_own_feedback(self, client, db_session, test_user, superuser, user_headers):
        db_session.add_all(
            [
                FeedbackModel(
                    id=uuid.uuid4(), user_id=test_user.id, type="bug", message="mine"
                ),
                FeedbackModel(
                    id=uuid.uuid4(), user_id=superuser.id, type="other", message="not mine"
                ),
            ]
        )
        await db_session.commit()
        resp = await client.get("/api/feedback", headers=user_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["message"] == "mine"
