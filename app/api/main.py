import uuid
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.rate_limit import AuthRateLimitMiddleware, limiter
from app.api.routes import auth_refresh, ats, cover_letter, history, master_cvs, parse, preview, qa, structure, tailor, templates
from app.auth.config import auth_backend, fastapi_users
from app.auth.schemas import UserCreate, UserRead, UserUpdate
from app.config import settings
from app.logging_config import configure_logging

configure_logging(settings.env)

STATIC_DIR = Path(__file__).parent.parent / "static"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'; "
            # blob: lets the in-app PDF preview render the rendered-CV blob in an iframe.
            "frame-src 'self' blob:; object-src 'self' blob:; base-uri 'self'",
        )
        # Only assert HSTS when actually served over HTTPS.
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def create_app() -> FastAPI:
    is_prod = settings.env == "production"
    app = FastAPI(
        title="CV Tailor",
        description="Tailor your CV to any job description in seconds.",
        version="1.0.0",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    # Rate limiting: SlowAPI for per-user LLM limits, custom middleware for auth.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(AuthRateLimitMiddleware)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    allowed = [h.strip() for h in settings.allowed_hosts.split(",") if h.strip()]
    if allowed and allowed != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed)

    # Auth routes
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth/jwt",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )
    # Refresh-token endpoints (/auth/login, /auth/refresh, /auth/logout).
    app.include_router(auth_refresh.router, tags=["auth"])

    # API routes
    app.include_router(parse.router, prefix="/api")
    app.include_router(tailor.router, prefix="/api")
    app.include_router(preview.router, prefix="/api")
    app.include_router(history.router, prefix="/api")
    app.include_router(structure.router, prefix="/api")
    app.include_router(qa.router, prefix="/api")
    app.include_router(ats.router, prefix="/api")
    app.include_router(master_cvs.router, prefix="/api")
    app.include_router(cover_letter.router, prefix="/api")
    app.include_router(templates.router, prefix="/api")

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    # Static SPA mount — must be last so /api, /auth, /users take priority.
    # html=True serves index.html for `/`; the exception handler below catches
    # 404s on other client-side routes (e.g. /login, /history) and falls back
    # to index.html so React Router can resolve them.
    if STATIC_DIR.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(STATIC_DIR), html=True),
            name="static",
        )

        @app.exception_handler(StarletteHTTPException)
        async def spa_fallback(request: Request, exc: StarletteHTTPException):
            if exc.status_code == 404:
                path = request.url.path
                if not path.startswith(("/api", "/auth", "/users", "/static", "/assets", "/docs", "/redoc", "/openapi")):
                    return FileResponse(str(STATIC_DIR / "index.html"))
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    return app


app = create_app()
