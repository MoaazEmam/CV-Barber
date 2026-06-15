"""Per-user LLM keys: CRUD scoping, route masking, and the BYO rate-limit switch."""
import uuid

import pytest
import pytest_asyncio
from fastapi_users.password import PasswordHelper

from app.api.dependencies import (
    create_user_llm_key,
    delete_user_llm_key,
    list_user_llm_keys,
    user_has_llm_keys,
)
from app.db.models import User
from app.services.crypto import encrypt


@pytest_asyncio.fixture
async def other_user(db_session):
    user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
        email="other@cvbarber.dev",
        username="otheruser",
        hashed_password=PasswordHelper().hash("otherpassword"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


class TestLLMKeyCRUD:
    async def test_create_list_and_scope(self, db_session, test_user, other_user):
        await create_user_llm_key(
            db_session, test_user.id, "groq", encrypt("sk-a"), key_hint="sk-a"[-4:], label="mine"
        )
        mine = await list_user_llm_keys(db_session, test_user.id)
        assert len(mine) == 1
        assert mine[0].provider == "groq"
        # Other user can't see it.
        assert await list_user_llm_keys(db_session, other_user.id) == []
        assert await user_has_llm_keys(db_session, test_user.id) is True
        assert await user_has_llm_keys(db_session, other_user.id) is False

    async def test_delete_is_user_scoped(self, db_session, test_user, other_user):
        row = await create_user_llm_key(
            db_session, test_user.id, "groq", encrypt("sk-a"), key_hint="sk-a"
        )
        with pytest.raises(KeyError):
            await delete_user_llm_key(db_session, row.id, other_user.id)  # not theirs
        await delete_user_llm_key(db_session, row.id, test_user.id)
        assert await list_user_llm_keys(db_session, test_user.id) == []


class TestLLMKeyRoutes:
    async def test_post_validates_stores_and_masks(self, client, user_headers, monkeypatch):
        # Skip the live provider call so the test is offline + deterministic.
        async def _ok(provider, key):
            return None

        monkeypatch.setattr("app.api.routes.llm_keys._validate_key", _ok)

        resp = await client.post(
            "/api/llm-keys",
            headers=user_headers,
            json={"provider": "groq", "key": "sk-secret-123456", "label": "personal"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["provider"] == "groq"
        assert body["key_hint"] == "3456"
        # The plaintext secret must never come back.
        assert "key" not in body or body.get("key") != "sk-secret-123456"

        listed = await client.get("/api/llm-keys", headers=user_headers)
        assert listed.status_code == 200
        data = listed.json()
        assert "groq" in data["providers"]
        assert len(data["keys"]) == 1
        assert data["keys"][0]["key_hint"] == "3456"
        assert "sk-secret-123456" not in listed.text

    async def test_post_rejects_unknown_provider(self, client, user_headers):
        resp = await client.post(
            "/api/llm-keys",
            headers=user_headers,
            json={"provider": "definitely-not-real", "key": "sk-secret-123456"},
        )
        assert resp.status_code == 400

    async def test_announcement_flag_settable_via_users_me(self, client, user_headers):
        resp = await client.patch(
            "/users/me", headers=user_headers, json={"has_seen_llm_keys_announcement": True}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["has_seen_llm_keys_announcement"] is True


class TestBYORateLimitSwitch:
    def test_llm_rate_limit_uses_byo_ceiling_when_flagged(self):
        from app.api.rate_limit import llm_rate_limit, set_byo_request
        from app.config import settings

        set_byo_request(False)
        assert llm_rate_limit() == settings.llm_user_rate_limits
        set_byo_request(True)
        assert llm_rate_limit() == settings.llm_byo_user_rate_limits
        set_byo_request(False)  # reset
