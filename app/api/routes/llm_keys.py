"""Bring-your-own LLM API keys: list / add / delete a user's own provider keys.

Keys are validated with one cheap live completion, encrypted at rest, and never
returned in plaintext (only a last-4 hint). The fall-back preference and the
one-time announcement flag are user fields managed via PATCH /users/me.
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    create_user_llm_key,
    delete_user_llm_key,
    list_user_llm_keys,
)
from app.api.rate_limit import limiter
from app.auth.config import current_active_user
from app.config import SUPPORTED_BYO_PROVIDERS, settings
from app.db.dependencies import get_db
from app.db.models import User
from app.llm.client_factory import _build_user_leaf
from app.llm.exceptions import LLMAllKeysExhaustedError, LLMRateLimitError
from app.services.crypto import encrypt

router = APIRouter()
log = structlog.get_logger()

MAX_KEYS_PER_USER = 10


_PROVIDER_NAMES = {
    "groq": "Groq",
    "gemini": "Google Gemini",
    "cerebras": "Cerebras",
    "nvidia": "NVIDIA",
    "mistral": "Mistral",
    "openrouter": "OpenRouter",
    "zai": "Z.AI",
}

# Substrings that mean "the key itself is wrong" across the various provider SDKs.
_AUTH_ERROR_MARKERS = (
    "invalid api key", "api key not valid", "invalid_api_key", "incorrect api key",
    "no auth credentials", "unauthorized", "permission denied", "authentication",
    "401", "403",
)


def _friendly_validation_error(provider: str, exc: Exception) -> str:
    """Turn a raw provider SDK error into a clean, user-facing message (the raw
    detail is logged separately, never surfaced)."""
    name = _PROVIDER_NAMES.get(provider, provider.title())
    text = str(exc).lower()
    if any(marker in text for marker in _AUTH_ERROR_MARKERS):
        return f"That {name} API key doesn't look valid. Double-check you copied the whole key, then try again."
    return f"We couldn't verify your {name} key right now. Check the key and your connection, then try again."


class LLMKeyCreate(BaseModel):
    provider: str
    key: str = Field(min_length=8)
    label: str | None = Field(default=None, max_length=60)


class LLMKeyRead(BaseModel):
    id: UUID
    provider: str
    label: str | None
    key_hint: str | None


async def _validate_key(provider: str, key: str) -> None:
    """Prove the key works with one cheap completion. A throttled-but-valid key is
    accepted; anything else (bad auth, unknown provider) is rejected."""
    client = _build_user_leaf(provider, [key])
    if client is None:
        raise HTTPException(status_code=400, detail=f"Unsupported provider '{provider}'.")
    try:
        await client.complete("You are a connectivity test.", "Reply with the word ok.")
    except (LLMRateLimitError, LLMAllKeysExhaustedError):
        return  # valid key, just rate-limited right now
    except Exception as exc:  # auth failure / bad key / network
        # Log the raw provider error for debugging; show the user a clean message.
        log.info("user_llm_key_validation_failed", provider=provider, error=str(exc)[:200])
        raise HTTPException(
            status_code=400, detail=_friendly_validation_error(provider, exc)
        ) from exc


@router.get("/llm-keys")
async def get_llm_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    rows = await list_user_llm_keys(db, current_user.id)
    return {
        "providers": SUPPORTED_BYO_PROVIDERS,
        "fallback_to_shared": current_user.llm_fallback_to_shared,
        "keys": [
            LLMKeyRead(id=r.id, provider=r.provider, label=r.label, key_hint=r.key_hint)
            for r in rows
        ],
    }


@router.post("/llm-keys", status_code=201)
@limiter.limit("10/minute")
async def add_llm_key(
    request: Request,
    payload: LLMKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    provider = payload.provider.strip().lower()
    if provider not in SUPPORTED_BYO_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider '{provider}'.")

    existing = await list_user_llm_keys(db, current_user.id)
    if len(existing) >= MAX_KEYS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"You can store at most {MAX_KEYS_PER_USER} keys. Delete one first.",
        )

    key = payload.key.strip()
    await _validate_key(provider, key)

    row = await create_user_llm_key(
        db, current_user.id,
        provider=provider,
        encrypted_key=encrypt(key),
        key_hint=key[-4:],
        label=(payload.label or None),
    )
    log.info("user_llm_key_added", user_id=str(current_user.id), provider=provider)
    return LLMKeyRead(id=row.id, provider=row.provider, label=row.label, key_hint=row.key_hint)


@router.delete("/llm-keys/{key_id}")
async def remove_llm_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    try:
        await delete_user_llm_key(db, key_id, current_user.id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Key not found.")
    return {"ok": True}
