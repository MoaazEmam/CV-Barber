"""Symmetric encryption for stored secrets (app.services.crypto)."""
import pytest

from app.services.crypto import DecryptionError, decrypt, encrypt


def test_round_trip():
    secret = "sk-or-v1-abcdef0123456789"
    token = encrypt(secret)
    assert token != secret  # actually encrypted
    assert decrypt(token) == secret


def test_distinct_ciphertexts():
    # Fernet embeds a random IV, so the same plaintext encrypts differently.
    assert encrypt("same") != encrypt("same")


def test_garbage_raises_decryption_error():
    with pytest.raises(DecryptionError):
        decrypt("not-a-valid-fernet-token")
