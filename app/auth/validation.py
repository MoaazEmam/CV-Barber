"""Pure auth input validators (no DB/app deps, so they're trivially testable).

Kept separate from ``manager.py`` to avoid the ``config <-> manager`` import
cycle when imported directly (e.g. from tests).
"""

import re

from fastapi import HTTPException

USERNAME_RE = re.compile(r"^[A-Za-z0-9]+$")
USERNAME_MIN = 3
USERNAME_MAX = 30


def validate_username(username: str) -> None:
    """Enforce the username policy: letters + numbers only, 3–30 chars.

    Raises HTTPException(400) with a user-facing message so the frontend can
    show the reason directly — same pattern as the "already taken" check.
    """
    name = username or ""
    if len(name) < USERNAME_MIN:
        raise HTTPException(
            status_code=400,
            detail=f"Username must be at least {USERNAME_MIN} characters long.",
        )
    if len(name) > USERNAME_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Username must be at most {USERNAME_MAX} characters long.",
        )
    if not USERNAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="Username can only contain letters and numbers.",
        )
