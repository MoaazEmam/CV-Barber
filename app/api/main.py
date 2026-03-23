from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.api.routes import parse, tailor, preview

STATIC_DIR = Path(__file__).parent.parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="CV Tailor",
        description="Tailor your CV to any job description in seconds.",
        version="1.0.0",
    )

    # API routes
    app.include_router(parse.router, prefix="/api")
    app.include_router(tailor.router, prefix="/api")
    app.include_router(preview.router, prefix="/api")

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def root():
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}
    return app


app = create_app()