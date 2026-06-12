"""Email verification endpoints (authenticated, but not verified-required).

- ``POST /auth/request-verify-code`` : (re)send a 6-digit code to the user's email.
- ``POST /auth/verify-code``         : submit the code; sets ``is_verified``.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.config import current_active_user
from app.auth.schemas import UserRead
from app.db.dependencies import get_db
from app.db.models import User
from app.services.email import EmailSendError
from app.services.verification import (
    VerificationError,
    check_verification_code,
    issue_verification_code,
)

router = APIRouter()
logger = structlog.get_logger()


class VerifyCodeRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


@router.post("/auth/request-verify-code")
async def request_verify_code(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db),
):
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified.")
    try:
        await issue_verification_code(session, user)
    except VerificationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except EmailSendError:
        raise HTTPException(
            status_code=502, detail="Could not send the email. Please try again."
        )
    return {"detail": "sent"}


@router.post("/auth/verify-code", response_model=UserRead)
async def verify_code(
    body: VerifyCodeRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db),
):
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified.")
    try:
        await check_verification_code(session, user, body.code)
    except VerificationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    user.is_verified = True
    session.add(user)
    await session.commit()
    await session.refresh(user)
    await logger.ainfo("email_verified", user_id=str(user.id))
    return user
