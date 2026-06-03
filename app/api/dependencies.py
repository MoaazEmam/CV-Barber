from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApplicationModel, MasterCVModel, QAResponseModel
from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV


async def save_master_cv(
    db: AsyncSession,
    master_cv: MasterCV,
    raw_file: bytes,
    file_type: str,
    user_id: UUID,
    text_hash: str | None = None,
) -> UUID:
    row = MasterCVModel(
        id=uuid4(),
        user_id=user_id,
        raw_file=raw_file,
        file_type=file_type,
        parsed_data=master_cv.model_dump(),
        text_hash=text_hash,
        is_active=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row.id


async def get_master_cv(db: AsyncSession, master_cv_id: UUID, user_id: UUID) -> MasterCV:
    result = await db.execute(
        select(MasterCVModel).where(
            MasterCVModel.id == master_cv_id,
            MasterCVModel.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"MasterCV {master_cv_id} not found")
    return MasterCV.model_validate(row.parsed_data)


async def save_application(
    db: AsyncSession,
    tailored_cv: TailoredCV,
    master_cv_id: UUID,
    job_title: str,
    company_name: str,
    job_description: str,
    user_id: UUID,
) -> UUID:
    row = ApplicationModel(
        id=uuid4(),
        user_id=user_id,
        master_cv_id=master_cv_id,
        job_title=job_title,
        company_name=company_name,
        job_description=job_description,
        tailored_cv_data=tailored_cv.model_dump(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row.id


async def get_application(db: AsyncSession, application_id: UUID, user_id: UUID) -> TailoredCV:
    result = await db.execute(
        select(ApplicationModel).where(
            ApplicationModel.id == application_id,
            ApplicationModel.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"Application {application_id} not found")
    return TailoredCV.model_validate(row.tailored_cv_data)


async def delete_application(db: AsyncSession, application_id: UUID, user_id: UUID) -> None:
    result = await db.execute(
        select(ApplicationModel).where(
            ApplicationModel.id == application_id,
            ApplicationModel.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"Application {application_id} not found")
    await db.execute(
        delete(QAResponseModel).where(QAResponseModel.application_id == application_id)
    )
    await db.delete(row)
    await db.commit()


async def delete_master_cv(db: AsyncSession, master_cv_id: UUID, user_id: UUID) -> None:
    mcv_result = await db.execute(
        select(MasterCVModel).where(
            MasterCVModel.id == master_cv_id,
            MasterCVModel.user_id == user_id,
        )
    )
    row = mcv_result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"MasterCV {master_cv_id} not found")
    app_result = await db.execute(
        select(ApplicationModel.id).where(
            ApplicationModel.master_cv_id == master_cv_id,
            ApplicationModel.user_id == user_id,
        )
    )
    app_ids = [r[0] for r in app_result.all()]
    if app_ids:
        await db.execute(
            delete(QAResponseModel).where(QAResponseModel.application_id.in_(app_ids))
        )
    await db.execute(
        delete(ApplicationModel).where(
            ApplicationModel.master_cv_id == master_cv_id,
            ApplicationModel.user_id == user_id,
        )
    )
    await db.delete(row)
    await db.commit()


async def list_master_cvs(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Return a lightweight list of the user's uploaded master CVs (no raw file bytes)."""
    result = await db.execute(
        select(MasterCVModel)
        .where(MasterCVModel.user_id == user_id)
        .order_by(MasterCVModel.created_at.desc())
    )
    rows = result.scalars().all()
    items = []
    for row in rows:
        data: dict = row.parsed_data or {}
        items.append(
            {
                "id": row.id,
                "full_name": data.get("full_name", ""),
                "experience_count": len(data.get("experience", [])),
                "project_count": len(data.get("projects", [])),
                "skills_count": len(data.get("skills", [])),
                "created_at": row.created_at,
            }
        )
    return items
