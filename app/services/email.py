"""Transactional email via the Brevo REST API.

One POST to https://api.brevo.com/v3/smtp/email (httpx, async). When
``BREVO_API_KEY`` is unset (dev/tests) nothing is sent; outside production the
verification code is logged so the flow remains testable end-to-end.
"""

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class EmailSendError(Exception):
    """Raised when the email provider rejects or fails the send."""


async def send_email(to: str, subject: str, html: str) -> None:
    if not settings.brevo_api_key:
        if settings.env != "production":
            await logger.awarning("email_send_skipped_no_api_key", to=to, subject=subject)
            return
        raise EmailSendError("Email provider is not configured.")

    payload = {
        "sender": {"email": settings.mail_from, "name": settings.mail_from_name},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                BREVO_SEND_URL,
                json=payload,
                headers={"api-key": settings.brevo_api_key},
            )
    except httpx.HTTPError as exc:
        await logger.aerror("email_send_failed", error=str(exc))
        raise EmailSendError("Could not reach the email provider.") from exc

    if response.status_code >= 300:
        await logger.aerror(
            "email_send_failed",
            status_code=response.status_code,
            body=response.text[:500],
        )
        raise EmailSendError("The email provider rejected the message.")
    await logger.ainfo("email_sent", subject=subject)


async def send_verification_code(to: str, code: str) -> None:
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #1a1a2e;">Verify your email</h2>
      <p>Use this code to verify your CV Barber account:</p>
      <p style="font-size: 32px; font-weight: bold; letter-spacing: 8px;
                background: #f4f4f8; padding: 16px; text-align: center;
                border-radius: 8px;">{code}</p>
      <p style="color: #666;">The code expires in 15 minutes. If you didn't
      request this, you can ignore this email.</p>
    </div>
    """
    if not settings.brevo_api_key and settings.env != "production":
        # Dev fallback: surface the code in server logs so the flow is testable.
        await logger.awarning("verification_code_dev_log", to=to, code=code)
        return
    await send_email(to, "Your CV Barber verification code", html)


async def send_password_reset(to: str, reset_link: str) -> None:
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #1a1a2e;">Reset your password</h2>
      <p>We received a request to reset the password for your CV Barber
      account. Click the button below to choose a new one:</p>
      <p style="text-align: center; margin: 24px 0;">
        <a href="{reset_link}" style="background: #5E6AD2; color: #ffffff;
           padding: 12px 28px; border-radius: 8px; text-decoration: none;
           font-weight: bold; display: inline-block;">Reset password</a>
      </p>
      <p style="color: #666;">The link expires in 1 hour. If you didn't
      request this, you can safely ignore this email — your password won't
      change.</p>
    </div>
    """
    if not settings.brevo_api_key and settings.env != "production":
        # Dev fallback: surface the link in server logs so the flow is testable.
        await logger.awarning("password_reset_dev_log", to=to, link=reset_link)
        return
    await send_email(to, "Reset your CV Barber password", html)
