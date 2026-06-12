"""Refresh-token endpoints (additive — the generated /auth/jwt/login still works).

- ``POST /auth/login``   : authenticate, return an access token, and set a
  long-lived httpOnly ``refresh_token`` cookie (scoped to ``/auth``).
- ``POST /auth/refresh`` : exchange the refresh cookie for a fresh access token.
- ``POST /auth/logout``  : clear the refresh cookie.

The refresh token is httpOnly (not readable by JS) and uses a distinct JWT
audience, so it can't be replayed as an access token.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.config import (
    REFRESH_TOKEN_LIFETIME,
    current_active_user,
    get_jwt_strategy,
    get_refresh_strategy,
)
from app.auth.manager import get_user_manager
from app.config import settings
from app.db.models import User

router = APIRouter()
logger = structlog.get_logger()

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/auth"


def _set_refresh_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=REFRESH_TOKEN_LIFETIME,
        httponly=True,
        secure=settings.env == "production",
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


@router.post("/auth/login")
async def login_with_refresh(
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager=Depends(get_user_manager),
):
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=400, detail="Incorrect email/username or password."
        )

    access = await get_jwt_strategy().write_token(user)
    refresh = await get_refresh_strategy().write_token(user)
    response = JSONResponse({"access_token": access, "token_type": "bearer"})
    _set_refresh_cookie(response, refresh)
    return response


@router.post("/auth/refresh")
async def refresh_access_token(
    request: Request,
    user_manager=Depends(get_user_manager),
):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token.")

    user = await get_refresh_strategy().read_token(token, user_manager)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    access = await get_jwt_strategy().write_token(user)
    return {"access_token": access, "token_type": "bearer"}


@router.post("/auth/cookie")
async def issue_refresh_cookie(user: User = Depends(current_active_user)):
    """Mint the refresh cookie for an already-authenticated session.

    Used after Google OAuth: the SPA receives only an access token in the
    redirect fragment, then calls this so the session survives like a normal
    password login.
    """
    refresh = await get_refresh_strategy().write_token(user)
    response = JSONResponse({"ok": True})
    _set_refresh_cookie(response, refresh)
    return response


@router.post("/auth/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    return response
