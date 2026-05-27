from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import ApplicationDetail, ApplicationSummary, HistoryResponse
from app.auth.config import current_active_user
from app.db.dependencies import get_db
from app.db.models import ApplicationModel, MasterCVModel, User

router = APIRouter()


@router.get("/history", response_model=HistoryResponse)
async def list_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    result = await db.execute(
        select(ApplicationModel)
        .where(ApplicationModel.user_id == current_user.id)
        .order_by(ApplicationModel.created_at.desc())
    )
    rows = result.scalars().all()
    return HistoryResponse(
        applications=[
            ApplicationSummary(
                id=row.id,
                job_title=row.job_title,
                company_name=row.company_name,
                created_at=row.created_at,
                job_match_score=row.job_match_score,
            )
            for row in rows
        ]
    )


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
async def get_application_detail(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    result = await db.execute(
        select(ApplicationModel).where(ApplicationModel.id == application_id)
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise HTTPException(status_code=404, detail="Not found")
    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    mcv_result = await db.execute(
        select(MasterCVModel).where(MasterCVModel.id == application.master_cv_id)
    )
    master = mcv_result.scalar_one_or_none()
    return ApplicationDetail(
        id=application.id,
        master_cv_id=application.master_cv_id,
        job_title=application.job_title,
        company_name=application.company_name,
        job_description=application.job_description,
        created_at=application.created_at,
        tailored_cv_data=application.tailored_cv_data,
        job_match_score=application.job_match_score,
        job_improvement_points=application.job_improvement_points,
        general_ats_score=master.general_ats_score if master else None,
        ats_improvement_points=master.ats_improvement_points if master else None,
        section_config=application.section_config,
        cover_letter=application.cover_letter,
    )
