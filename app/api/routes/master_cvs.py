from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import MasterCVListItem, MasterCVListResponse
from app.auth.config import current_active_user
from app.db.dependencies import get_db
from app.db.models import MasterCVModel, User

router = APIRouter()


@router.get("/master-cvs", response_model=MasterCVListResponse)
async def list_master_cvs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    result = await db.execute(
        select(MasterCVModel)
        .where(MasterCVModel.user_id == current_user.id)
        .order_by(MasterCVModel.created_at.desc())
    )
    rows = result.scalars().all()
    items = []
    for row in rows:
        data = row.parsed_data or {}
        items.append(
            MasterCVListItem(
                id=row.id,
                full_name=data.get("full_name", ""),
                experience_count=len(data.get("experience", [])),
                project_count=len(data.get("projects", [])),
                skills_count=len(data.get("skills", [])),
                created_at=row.created_at,
            )
        )
    return MasterCVListResponse(master_cvs=items)
