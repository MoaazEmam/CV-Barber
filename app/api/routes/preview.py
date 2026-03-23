from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from app.api.dependencies import SessionStore, get_session_store

router = APIRouter()

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "generation" / "templates"


@router.get("/preview/{tailored_id}", response_class=HTMLResponse)
async def preview_cv(
    tailored_id: str,
    store: SessionStore = Depends(get_session_store),
):
    tailored_cv = store.get_tailored(tailored_id)
    if not tailored_cv:
        raise HTTPException(status_code=404, detail="Tailored CV not found.")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("cv.html")
    html = template.render(cv=tailored_cv)
    return HTMLResponse(content=html)