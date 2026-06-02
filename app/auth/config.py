import uuid

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.dependencies import get_db
from app.db.models import User


async def get_user_db(session: AsyncSession = Depends(get_db)):
    yield SQLAlchemyUserDatabase(session, User)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


ACCESS_TOKEN_AUDIENCE = "fastapi-users:auth"
REFRESH_TOKEN_AUDIENCE = "cvbarber:refresh"
REFRESH_TOKEN_LIFETIME = 60 * 60 * 24 * 14  # 14 days


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key,
        lifetime_seconds=3600,
        token_audience=[ACCESS_TOKEN_AUDIENCE],
    )


def get_refresh_strategy() -> JWTStrategy:
    # Distinct audience so an access token can never be used as a refresh token
    # (and vice versa), even though both are signed with the same secret.
    return JWTStrategy(
        secret=settings.secret_key,
        lifetime_seconds=REFRESH_TOKEN_LIFETIME,
        token_audience=[REFRESH_TOKEN_AUDIENCE],
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

from app.auth.manager import get_user_manager

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)
