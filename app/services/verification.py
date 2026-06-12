"""Email-verification code lifecycle: issue, resend limits, and checking.

One row per user in ``email_verification_codes`` (hashed code, 15-minute
expiry, 5-attempt cap, 60s resend cooldown, 5 sends/hour).
"""

import hashlib
import secrets
from datetime import datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EmailVerificationCode, User
from app.services.email import send_verification_code

logger = structlog.get_logger()

CODE_TTL = timedelta(minutes=15)
RESEND_COOLDOWN_SECONDS = 60
MAX_SENDS_PER_HOUR = 5
MAX_ATTEMPTS = 5


class VerificationError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def _get_row(session: AsyncSession, user_id) -> EmailVerificationCode | None:
    result = await session.execute(
        select(EmailVerificationCode).where(EmailVerificationCode.user_id == user_id)
    )
    return result.scalars().first()


async def issue_verification_code(session: AsyncSession, user: User) -> None:
    """Generate, store (hashed), and email a fresh 6-digit code.

    Enforces the resend cooldown and hourly send cap. Commits before sending so
    a slow/failed email never loses the stored code.
    """
    now = datetime.utcnow()
    row = await _get_row(session, user.id)

    if row is not None:
        elapsed = (now - row.last_sent_at).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            raise VerificationError(
                "Please wait a minute before requesting another code.", 429
            )
        if elapsed < 3600 and row.send_count >= MAX_SENDS_PER_HOUR:
            raise VerificationError(
                "Too many codes requested. Please try again in an hour.", 429
            )

    code = f"{secrets.randbelow(1_000_000):06d}"
    if row is None:
        row = EmailVerificationCode(user_id=user.id, send_count=0, last_sent_at=now)
        session.add(row)
    elif (now - row.last_sent_at).total_seconds() >= 3600:
        row.send_count = 0  # new hourly window

    row.code_hash = _hash_code(code)
    row.expires_at = now + CODE_TTL
    row.attempts = 0
    row.last_sent_at = now
    row.send_count += 1
    await session.commit()

    await send_verification_code(user.email, code)
    await logger.ainfo("verification_code_sent", user_id=str(user.id))


async def check_verification_code(session: AsyncSession, user: User, code: str) -> None:
    """Validate the submitted code; raises VerificationError on any failure.

    On success the stored row is deleted (caller flips ``is_verified``).
    """
    row = await _get_row(session, user.id)
    now = datetime.utcnow()

    if row is None or row.expires_at < now:
        raise VerificationError("Code expired. Please request a new one.")
    if row.attempts >= MAX_ATTEMPTS:
        raise VerificationError("Too many attempts. Please request a new code.")

    if not secrets.compare_digest(_hash_code(code), row.code_hash):
        row.attempts += 1
        await session.commit()
        raise VerificationError("Incorrect code.")

    await session.delete(row)
    await session.commit()
