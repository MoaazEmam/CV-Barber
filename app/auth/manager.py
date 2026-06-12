import uuid
from typing import Optional, Union

import structlog
from fastapi import Depends, HTTPException, Request
from fastapi_users import BaseUserManager, InvalidPasswordException, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserCreate
from app.auth.validation import validate_username
from app.config import settings
from app.db.dependencies import get_db
from app.db.models import OAuthAccount, User


async def get_user_db(session: AsyncSession = Depends(get_db)):
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

logger = structlog.get_logger()

# Per-user cooldown on password-reset emails (in-process, like the auth rate
# limiter). /auth/forgot-password always returns 202, so the brute-force
# middleware never counts it — this stops one address being spammed instead.
RESET_EMAIL_COOLDOWN_SECONDS = 60
_last_reset_email_at: dict[str, float] = {}


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

    async def update(
        self,
        user_update,
        user: User,
        safe: bool = False,
        request: Optional[Request] = None,
    ) -> User:
        # Username changes (incl. the post-OAuth "choose username" flow) get the
        # same validation + case-insensitive uniqueness check as registration.
        # exclude_unset means an omitted username is "no change"; an explicit
        # null would clear it, which we forbid.
        update_dict = user_update.create_update_dict() if safe else user_update.create_update_dict_superuser()
        if "username" in update_dict:
            new_username = update_dict["username"]
            if new_username is None:
                raise HTTPException(status_code=400, detail="Username cannot be removed.")
            validate_username(new_username)
            result = await self.user_db.session.execute(
                select(User).where(
                    func.lower(User.username) == new_username.lower(),
                    User.id != user.id,
                )
            )
            if result.scalars().first() is not None:
                raise HTTPException(status_code=400, detail="That username is already taken.")
        return await super().update(user_update, user, safe=safe, request=request)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        import time

        from app.services.email import send_password_reset

        now = time.monotonic()
        last = _last_reset_email_at.get(str(user.id))
        if last is not None and now - last < RESET_EMAIL_COOLDOWN_SECONDS:
            await logger.ainfo("password_reset_email_throttled", user_id=str(user.id))
            return
        _last_reset_email_at[str(user.id)] = now

        reset_link = f"{settings.app_base_url}/reset-password?token={token}"
        # The endpoint always answers 202; a send failure is logged, not surfaced
        # (the user can simply retry after the cooldown).
        try:
            await send_password_reset(user.email, reset_link)
            await logger.ainfo("password_reset_email_sent", user_id=str(user.id))
        except Exception as exc:
            await logger.awarning(
                "password_reset_email_failed", user_id=str(user.id), error=str(exc)
            )

    async def on_after_reset_password(
        self, user: User, request: Optional[Request] = None
    ):
        await logger.ainfo("password_reset_completed", user_id=str(user.id))

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        await logger.ainfo("user_registered", user_id=str(user.id))
        # Email/password signups start unverified -> send the first code. OAuth
        # users are created already verified, so this is skipped for them.
        # Registration must never fail because the email couldn't be sent (the
        # user can hit "resend" from the verify screen).
        if not user.is_verified:
            from app.services.verification import issue_verification_code

            try:
                await issue_verification_code(self.user_db.session, user)
            except Exception as exc:
                await logger.awarning(
                    "verification_email_failed_on_register",
                    user_id=str(user.id),
                    error=str(exc),
                )


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)
