"""Dedup hashing.

The cache key for a CV is a SHA-256 over its normalised raw text. Identical
uploads hash identically and reuse the stored ``(parsed_data, template_artifact,
section_map)`` — skipping every Tier 1 LLM call. The lookup itself lives in the
route (it needs the DB session + user); this module owns the normalise+hash
contract so it stays consistent everywhere.
"""

from __future__ import annotations

import hashlib


def normalize(text: str) -> str:
    """Collapse all whitespace and lowercase — the canonical form we hash."""
    return " ".join(text.split()).lower()


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()
