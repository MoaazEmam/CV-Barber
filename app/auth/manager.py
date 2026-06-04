import uuid
from typing import Optional, Union

import structlog
from fastapi import Depends, HTTPException, Request
from fastapi_users import BaseUserManager, InvalidPasswordException, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import func, select

from app.auth.config import get_user_db
from app.auth.schemas import UserCreate
from app.auth.validation import validate_username
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

    async def create(
        self,
        user_create: UserCreate,
        safe: bool = False,
        request: Optional[Request] = None,
    ) -> User:
        validate_username(user_create.username)
        # Reject case-insensitive username clashes with a clear message before the
        # base class inserts the row — otherwise the unique index on
        # lower(username) raises an opaque IntegrityError (HTTP 500). The unique
        # index remains the source of truth (this is just for a friendly error).
        result = await self.user_db.session.execute(
            select(User).where(
                func.lower(User.username) == user_create.username.lower()
            )
        )
        if result.scalars().first() is not None:
            raise HTTPException(status_code=400, detail="That username is already taken.")
        return await super().create(user_create, safe=safe, request=request)

    async def authenticate(self, credentials) -> Optional[User]:
        user = None
        try:
            user = await self.user_db.get_by_email(credentials.username)
        except Exception:
            pass

        if user is None:
            # Case-insensitive username match (email lookup above already is).
            result = await self.user_db.session.execute(
                select(User).where(
                    func.lower(User.username) == credentials.username.lower()
                )
            )
            user = result.scalars().first()

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
