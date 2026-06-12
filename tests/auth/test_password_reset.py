"""Forgot/reset password flow (UserManager hooks + fastapi-users reset)."""
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase

import app.auth.manager as manager_module
import app.services.email as email_module
from app.auth.manager import UserManager
from app.db.models import OAuthAccount, User


@pytest.fixture
def manager(db_session):
    manager_module._last_reset_email_at.clear()
    return UserManager(SQLAlchemyUserDatabase(db_session, User, OAuthAccount))


@pytest.fixture
def sent_links(monkeypatch):
    links: list[str] = []

    async def fake_send(to: str, reset_link: str) -> None:
        links.append(reset_link)

    monkeypatch.setattr(email_module, "send_password_reset", fake_send)
    return links


def _token_from_link(link: str) -> str:
    return parse_qs(urlparse(link).query)["token"][0]


class TestForgotPassword:
    async def test_sends_reset_link_with_token(self, manager, test_user, sent_links):
        await manager.forgot_password(test_user)
        assert len(sent_links) == 1
        assert "/reset-password?token=" in sent_links[0]
        assert _token_from_link(sent_links[0])

    async def test_resend_throttled(self, manager, test_user, sent_links):
        await manager.forgot_password(test_user)
        await manager.forgot_password(test_user)
        assert len(sent_links) == 1  # second send suppressed by the cooldown

    async def test_reset_roundtrip_changes_password(self, manager, test_user, sent_links):
        await manager.forgot_password(test_user)
        token = _token_from_link(sent_links[0])
        await manager.reset_password(token, "newpassword123")
        verified, _ = manager.password_helper.verify_and_update(
            "newpassword123", test_user.hashed_password
        )
        assert verified

    async def test_reset_enforces_password_policy(self, manager, test_user, sent_links):
        from fastapi_users.exceptions import InvalidPasswordException

        await manager.forgot_password(test_user)
        token = _token_from_link(sent_links[0])
        with pytest.raises(InvalidPasswordException):
            await manager.reset_password(token, "short")

    async def test_bad_token_rejected(self, manager, test_user):
        from fastapi_users.exceptions import InvalidResetPasswordToken

        with pytest.raises(InvalidResetPasswordToken):
            await manager.reset_password("not-a-real-token", "newpassword123")
