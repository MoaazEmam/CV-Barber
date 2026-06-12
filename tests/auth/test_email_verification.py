"""Email verification code lifecycle (app.services.verification)."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

import app.services.verification as verification
from app.db.models import EmailVerificationCode
from app.services.verification import (
    VerificationError,
    check_verification_code,
    issue_verification_code,
)


@pytest.fixture
def sent_codes(monkeypatch):
    """Capture codes instead of emailing them."""
    codes: list[str] = []

    async def fake_send(to: str, code: str) -> None:
        codes.append(code)

    monkeypatch.setattr(verification, "send_verification_code", fake_send)
    return codes


async def _get_row(db_session, user_id):
    result = await db_session.execute(
        select(EmailVerificationCode).where(EmailVerificationCode.user_id == user_id)
    )
    return result.scalars().first()


class TestIssueCode:
    async def test_issue_stores_hashed_code_and_sends(self, db_session, test_user, sent_codes):
        await issue_verification_code(db_session, test_user)
        assert len(sent_codes) == 1
        assert len(sent_codes[0]) == 6 and sent_codes[0].isdigit()
        row = await _get_row(db_session, test_user.id)
        assert row is not None
        assert row.code_hash != sent_codes[0]  # stored hashed, not plaintext
        assert row.expires_at > datetime.utcnow()

    async def test_resend_cooldown(self, db_session, test_user, sent_codes):
        await issue_verification_code(db_session, test_user)
        with pytest.raises(VerificationError) as exc:
            await issue_verification_code(db_session, test_user)
        assert exc.value.status_code == 429
        assert len(sent_codes) == 1

    async def test_hourly_send_cap(self, db_session, test_user, sent_codes):
        await issue_verification_code(db_session, test_user)
        row = await _get_row(db_session, test_user.id)
        # Simulate 5 sends in the current window, last one past the cooldown.
        row.send_count = 5
        row.last_sent_at = datetime.utcnow() - timedelta(minutes=2)
        await db_session.commit()
        with pytest.raises(VerificationError) as exc:
            await issue_verification_code(db_session, test_user)
        assert exc.value.status_code == 429

    async def test_resend_after_cooldown_replaces_code(self, db_session, test_user, sent_codes):
        await issue_verification_code(db_session, test_user)
        row = await _get_row(db_session, test_user.id)
        row.last_sent_at = datetime.utcnow() - timedelta(minutes=2)
        await db_session.commit()
        await issue_verification_code(db_session, test_user)
        assert len(sent_codes) == 2
        # Old code no longer valid (unless identical by chance)
        if sent_codes[0] != sent_codes[1]:
            with pytest.raises(VerificationError):
                await check_verification_code(db_session, test_user, sent_codes[0])


class TestCheckCode:
    async def test_correct_code_deletes_row(self, db_session, test_user, sent_codes):
        await issue_verification_code(db_session, test_user)
        await check_verification_code(db_session, test_user, sent_codes[0])
        assert await _get_row(db_session, test_user.id) is None

    async def test_wrong_code_increments_attempts(self, db_session, test_user, sent_codes):
        await issue_verification_code(db_session, test_user)
        wrong = "000000" if sent_codes[0] != "000000" else "111111"
        with pytest.raises(VerificationError, match="Incorrect"):
            await check_verification_code(db_session, test_user, wrong)
        row = await _get_row(db_session, test_user.id)
        assert row.attempts == 1

    async def test_attempt_cap_blocks_even_correct_code(self, db_session, test_user, sent_codes):
        await issue_verification_code(db_session, test_user)
        row = await _get_row(db_session, test_user.id)
        row.attempts = 5
        await db_session.commit()
        with pytest.raises(VerificationError, match="Too many attempts"):
            await check_verification_code(db_session, test_user, sent_codes[0])

    async def test_expired_code_rejected(self, db_session, test_user, sent_codes):
        await issue_verification_code(db_session, test_user)
        row = await _get_row(db_session, test_user.id)
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        await db_session.commit()
        with pytest.raises(VerificationError, match="expired"):
            await check_verification_code(db_session, test_user, sent_codes[0])

    async def test_no_code_requested_rejected(self, db_session, test_user):
        with pytest.raises(VerificationError, match="expired"):
            await check_verification_code(db_session, test_user, "123456")
