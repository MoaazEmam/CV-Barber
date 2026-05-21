from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApplicationModel, MasterCVModel
from app.schemas.master_cv import MasterCV
from app.schemas.tailored_cv import TailoredCV


async def save_master_cv(
    db: AsyncSession,
    master_cv: MasterCV,
    raw_file: bytes,
    file_type: str,
    user_id: UUID,
) -> UUID:
    row = MasterCVModel(
        id=uuid4(),
        user_id=user_id,
        raw_file=raw_file,
        file_type=file_type,
        parsed_data=master_cv.model_dump(),
        is_active=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row.id


async def get_master_cv(db: AsyncSession, master_cv_id: UUID) -> MasterCV:
    result = await db.execute(
        select(MasterCVModel).where(MasterCVModel.id == master_cv_id)
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


async def get_application(db: AsyncSession, application_id: UUID) -> TailoredCV:
    result = await db.execute(
        select(ApplicationModel).where(ApplicationModel.id == application_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"Application {application_id} not found")
    return TailoredCV.model_validate(row.tailored_cv_data)
