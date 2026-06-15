"""Build LLM clients from a user's own stored API keys (bring-your-own-keys).

A request-scoped helper: it loads + decrypts the user's keys, groups them by
provider, and asks the factory for an uncached chain. When the user has no usable
keys it returns ``None`` so callers fall back to the shared app pool (the existing
behavior) by passing ``client=None`` to the LLM classes.
"""

from __future__ import annotations

from collections import defaultdict

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import list_user_llm_keys
from app.auth.config import current_active_user
from app.config import SUPPORTED_BYO_PROVIDERS
from app.db.dependencies import get_db
from app.db.models import User
from app.llm.base_client import BaseLLMClient
from app.llm.client_factory import LLMClientFactory
from app.services.crypto import DecryptionError, decrypt

log = structlog.get_logger()

# (provider -> list of plaintext keys, fall-back-to-shared flag)
KeyConfig = tuple[dict[str, list[str]], bool]


async def load_user_key_config(db: AsyncSession, user: User) -> KeyConfig:
    rows = await list_user_llm_keys(db, user.id)
    keys: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row.provider not in SUPPORTED_BYO_PROVIDERS:
            continue
        try:
            keys[row.provider].append(decrypt(row.encrypted_key))
        except DecryptionError:
            # Encryption key rotated or row corrupted — skip rather than crash.
            log.warning("user_llm_key_undecryptable", key_id=str(row.id), provider=row.provider)
    return dict(keys), bool(user.llm_fallback_to_shared)


def make_user_client(profile: str, config: KeyConfig) -> BaseLLMClient | None:
    user_keys, fallback = config
    if not user_keys:
        return None
    return LLMClientFactory.create(
        profile, user_keys=user_keys, fallback_to_shared=fallback
    )


async def build_user_llm_client(
    db: AsyncSession, user: User, profile: str
) -> BaseLLMClient | None:
    return make_user_client(profile, await load_user_key_config(db, user))


async def get_user_llm_client(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
) -> BaseLLMClient | None:
    """Dependency: returns the user's interactive client (or None) and records on
    ``request.state`` whether this is a BYO request (for the rate limiter) plus the
    loaded key config (so a route can build a different-profile client cheaply)."""
    from app.api.rate_limit import set_byo_request

    config = await load_user_key_config(db, user)
    is_byo = bool(config[0])
    request.state.byo_llm = is_byo
    request.state.user_key_config = config
    set_byo_request(is_byo)
    return make_user_client("interactive", config)
