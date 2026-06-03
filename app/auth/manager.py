import uuid
from typing import Optional, Union

import structlog
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, InvalidPasswordException, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import select

from app.auth.config import get_user_db
from app.auth.schemas import UserCreate
from app.config import settings
from app.db.models import User

logger = structlog.get_logger()


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def validate_password(
        self,
        password: str,
        user: Union[UserCreate, User],
    ) -> None:
        if len(password) < 8:
            raise InvalidPasswordException(
                reason="Password must be at least 8 characters long."
            )
        email = getattr(user, "email", None)
        if email and email.lower() in password.lower():
            raise InvalidPasswordException(
                reason="Password must not contain your email address."
            )

    async def authenticate(self, credentials) -> Optional[User]:
        user = None
        try:
            user = await self.user_db.get_by_email(credentials.username)
        except Exception:
            pass

        if user is None:
            result = await self.user_db.session.execute(
                select(User).where(User.username == credentials.username)
            )
            user = result.scalar_one_or_none()

        if user is None:
            self.password_helper.hash(credentials.password)
            return None

        verified, updated_password_hash = self.password_helper.verify_and_update(
            credentials.password, user.hashed_password
        )
        if not verified:
            return None
        if updated_password_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_password_hash})
        return user

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        await logger.ainfo("user_registered", user_id=str(user.id))


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)
