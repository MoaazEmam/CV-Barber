import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase

from app.auth.config import get_user_db
from app.config import settings
from app.db.models import User


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        import structlog
        logger = structlog.get_logger()
        await logger.ainfo("user_registered", user_id=str(user.id), email=user.email)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)
