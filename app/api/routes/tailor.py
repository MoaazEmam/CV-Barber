from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from app.api.dependencies import SessionStore, get_session_store
from app.api.models import TailorRequest, TailorResponse
from app.llm import CVScorer
from app.generation import GeneratorFactory
from app.schemas.config import TailoringConfig
from app.config import Settings, settings as default_settings

router = APIRouter()


@router.post("/tailor", response_model=TailorResponse)
async def tailor_cv(
    request: TailorRequest,
    store: SessionStore = Depends(get_session_store),
):
    master_cv = store.get_master(request.session_id)
    if not master_cv:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please upload your CV again."
        )

    config = TailoringConfig(
        job_title=request.job_title,
        company_name=request.company_name,
        top_n_experience=request.top_n_experience,
        top_n_projects=request.top_n_projects,
    )

    try:
        scorer = CVScorer()
        tailored_cv = scorer.score(master_cv, request.job_description, config)
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))

    tailored_id = store.save_tailored(tailored_cv)

    scores = [
        {
            "name": e.title,
            "type": "experience",
            "score": e.relevance_score,
            "reason": e.relevance_reason,
        }
        for e in tailored_cv.experience
    ] + [
        {
            "name": p.name,
            "type": "project",
            "score": p.relevance_score,
            "reason": p.relevance_reason,
        }
        for p in tailored_cv.projects
    ]

    return TailorResponse(
        session_id=request.session_id,
        tailored_session_id=tailored_id,
        full_name=tailored_cv.full_name,
        company_name=tailored_cv.company_name,
        job_title=tailored_cv.job_title,
        experience_count=len(tailored_cv.experience),
        project_count=len(tailored_cv.projects),
        tailored_summary=tailored_cv.tailored_summary,
        scores=scores,
    )


@router.get("/download/{tailored_id}")
async def download_cv(
    tailored_id: str,
    format: str = "docx",
    store: SessionStore = Depends(get_session_store),
):
    tailored_cv = store.get_tailored(tailored_id)
    if not tailored_cv:
        raise HTTPException(status_code=404, detail="Tailored CV not found.")

    # override settings format with query param
    override_settings = Settings(
        **{**default_settings.model_dump(), "output_format": format}
    )
    factory = GeneratorFactory(settings=override_settings)
    generator = factory.create()

    file_bytes = generator.generate(tailored_cv)
    filename = generator.filename(tailored_cv)

    return Response(
        content=file_bytes,
        media_type=generator.content_type(),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )