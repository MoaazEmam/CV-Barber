"""OAuth-related user model + username update rules (UserManager.update)."""
import uuid

import pytest
from fastapi import HTTPException
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.password import PasswordHelper

from app.auth.manager import UserManager
from app.auth.schemas import UserUpdate
from app.db.models import OAuthAccount, User


@pytest.fixture
def make_manager(db_session):
    def _make():
        return UserManager(SQLAlchemyUserDatabase(db_session, User, OAuthAccount))

    return _make


@pytest.fixture
async def oauth_user(db_session):
    """A Google-created user: verified, no username yet."""
    user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        email="google@cvbarber.dev",
        username=None,
        hashed_password=PasswordHelper().hash("irrelevant"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


class TestNullableUsername:
    async def test_user_can_exist_without_username(self, oauth_user):
        assert oauth_user.username is None
        assert oauth_user.is_verified is True

    async def test_choose_username(self, make_manager, oauth_user):
        updated = await make_manager().update(
            UserUpdate(username="googleuser1"), oauth_user, safe=True
        )
        assert updated.username == "googleuser1"

    async def test_duplicate_username_rejected_case_insensitive(
        self, make_manager, oauth_user, test_user
    ):
        with pytest.raises(HTTPException) as exc:
            await make_manager().update(
                UserUpdate(username="TESTUSER"), oauth_user, safe=True
            )
        assert exc.value.status_code == 400

    async def test_invalid_username_rejected(self, make_manager, oauth_user):
        with pytest.raises(HTTPException):
            await make_manager().update(
                UserUpdate(username="bad name!"), oauth_user, safe=True
            )

    async def test_cannot_clear_existing_username(self, make_manager, test_user):
        with pytest.raises(HTTPException) as exc:
            await make_manager().update(
                UserUpdate(username=None), test_user, safe=True
            )
        # exclude_unset semantics: an *explicit* null must be rejected, an
        # omitted username is fine.
        assert exc.value.status_code == 400

    async def test_omitted_username_is_no_change(self, make_manager, test_user):
        updated = await make_manager().update(UserUpdate(), test_user, safe=True)
        assert updated.username == "testuser"
