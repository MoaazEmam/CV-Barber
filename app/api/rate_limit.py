"""Rate limiting.

Two mechanisms, each scoped to where it fits:

- ``limiter`` (SlowAPI): per-user limits on the expensive LLM endpoints. The key
  is the authenticated user (JWT ``sub``), so one user/script can't burn the
  shared free-tier LLM token pool. Applied via ``@limiter.limit(...)`` decorators
  on the route handlers (which must take a ``request: Request`` argument).

- ``AuthRateLimitMiddleware``: a small IP-based sliding window on the login and
  register endpoints to blunt credential brute-force. Those routes are generated
  by FastAPI-Users and can't be decorated, so a middleware handles them.

Storage is in-process (single uvicorn worker), which matches the current Docker
deployment. If the app is ever scaled to multiple workers, move both to a shared
backend (e.g. Redis).
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

# Per-user limits for the LLM-backed endpoints (generous anti-abuse guardrail —
# the real ceiling is the shared provider token pool, surfaced to users as 429).
LLM_USER_LIMITS = "30/hour;80/day"

# Auth brute-force guard.
AUTH_PATHS = ("/auth/login", "/auth/jwt/login", "/auth/register")
AUTH_MAX_REQUESTS = 5
AUTH_WINDOW_SECONDS = 60


def user_or_ip_key(request: Request) -> str:
    """Key SlowAPI limits by authenticated user, falling back to client IP.

    The route's ``current_active_user`` dependency runs (and rejects invalid
    tokens with 401) before SlowAPI evaluates the limit, so by the time we read
    the token here it has already been verified — we only need the ``sub`` claim
    for keying, hence the unverified decode.
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        try:
            sub = jwt.get_unverified_claims(token).get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=user_or_ip_key)


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """IP-based sliding-window limit on the auth endpoints only."""

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        if request.url.path in AUTH_PATHS and request.method == "POST":
            ip = get_remote_address(request)
            now = time.time()
            with self._lock:
                hits = self._hits[ip]
                cutoff = now - AUTH_WINDOW_SECONDS
                while hits and hits[0] < cutoff:
                    hits.popleft()
                if len(hits) >= AUTH_MAX_REQUESTS:
                    retry_after = max(1, int(AUTH_WINDOW_SECONDS - (now - hits[0])))
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many attempts. Please try again shortly."},
                        headers={"Retry-After": str(retry_after)},
                    )
                hits.append(now)
        return await call_next(request)
