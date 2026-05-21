import uuid
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import ats, history, parse, preview, qa, structure, tailor
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="CV Tailor",
        description="Tailor your CV to any job description in seconds.",
        version="1.0.0",
    )

    app.add_middleware(RequestIDMiddleware)

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

    # API routes
    app.include_router(parse.router, prefix="/api")
    app.include_router(tailor.router, prefix="/api")
    app.include_router(preview.router, prefix="/api")
    app.include_router(history.router, prefix="/api")
    app.include_router(structure.router, prefix="/api")
    app.include_router(qa.router, prefix="/api")
    app.include_router(ats.router, prefix="/api")

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
