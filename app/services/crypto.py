"""Symmetric encryption for secrets at rest (currently per-user LLM API keys).

Uses Fernet (AES-128-CBC + HMAC) from the already-present ``cryptography`` package.
The key comes from ``LLM_KEY_ENCRYPTION_KEY`` (a Fernet key) when set; otherwise it
is derived deterministically from ``SECRET_KEY`` so local/dev works with no extra
config. Rotating either source makes existing ciphertext undecryptable — callers
catch :class:`DecryptionError` and treat the secret as unavailable rather than
crashing. Generate a dedicated key with ``Fernet.generate_key()``.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class DecryptionError(Exception):
    """Raised when ciphertext can't be decrypted (wrong/rotated key or corruption)."""


def _derive_key_from_secret(secret: str) -> bytes:
    # SHA-256 of the app secret -> 32 bytes -> url-safe base64 == a valid Fernet key.
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    configured = settings.llm_key_encryption_key
    key = configured.encode("utf-8") if configured else _derive_key_from_secret(settings.secret_key)
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise DecryptionError(str(exc)) from exc
