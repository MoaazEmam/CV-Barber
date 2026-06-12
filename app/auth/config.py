import uuid

from fastapi import Response
from fastapi.responses import RedirectResponse
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from httpx_oauth.clients.google import GoogleOAuth2

from app.config import settings
from app.db.models import User


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


class OAuthRedirectTransport(BearerTransport):
    """Hands the access token to the SPA after the OAuth callback.

    The token travels in the URL fragment, which browsers never send to the
    server (so it can't end up in access logs); the SPA reads it, scrubs the
    URL, and exchanges it for a refresh cookie via POST /auth/cookie.
    """

    async def get_login_response(self, token: str) -> Response:
        return RedirectResponse(
            f"{settings.app_base_url}/oauth-callback#token={token}",
            status_code=302,
        )


oauth_redirect_backend = AuthenticationBackend(
    name="jwt-oauth-redirect",
    transport=OAuthRedirectTransport(tokenUrl="auth/jwt/login"),
    get_strategy=get_jwt_strategy,
)

google_oauth_client = (
    GoogleOAuth2(settings.google_oauth_client_id, settings.google_oauth_client_secret)
    if settings.google_oauth_client_id and settings.google_oauth_client_secret
    else None
)

from app.auth.manager import get_user_manager

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend, oauth_redirect_backend],
)

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
