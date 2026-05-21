from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_master_cv
from app.api.models import CVStructureResponse, Section, SubSection
from app.auth.config import current_active_user
from app.db.dependencies import get_db
from app.db.models import User, MasterCVModel
from sqlalchemy import select

router = APIRouter()


@router.get("/cv/structure/{master_cv_id}", response_model=CVStructureResponse)
async def get_cv_structure(
    master_cv_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    result = await db.execute(
        select(MasterCVModel).where(MasterCVModel.id == master_cv_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="CV not found")
    if row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        master_cv = await get_master_cv(db, master_cv_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="CV not found")

    sections: list[Section] = []

    if master_cv.experience:
        sections.append(Section(
            key="experience",
            label="Experience",
            enabled=True,
            subsections=[
                SubSection(
                    key=f"experience.{i}",
                    label=f"{e.title} at {e.company}" if e.company else e.title,
                    enabled=True,
                )
                for i, e in enumerate(master_cv.experience)
            ],
        ))

    if master_cv.projects:
        sections.append(Section(
            key="projects",
            label="Projects",
            enabled=True,
            subsections=[
                SubSection(key=f"projects.{i}", label=p.name, enabled=True)
                for i, p in enumerate(master_cv.projects)
            ],
        ))

    if master_cv.skills:
        sections.append(Section(
            key="skills",
            label="Skills",
            enabled=True,
            subsections=[
                SubSection(key=f"skills.{i}", label=s.category, enabled=True)
                for i, s in enumerate(master_cv.skills)
            ],
        ))

    if master_cv.education:
        sections.append(Section(
            key="education",
            label="Education",
            enabled=True,
            subsections=[
                SubSection(
                    key=f"education.{i}",
                    label=f"{ed.degree} at {ed.institution}" if ed.degree else ed.institution,
                    enabled=True,
                )
                for i, ed in enumerate(master_cv.education)
            ],
        ))

    if getattr(master_cv, "certifications", None):
        sections.append(Section(
            key="certifications",
            label="Certifications",
            enabled=True,
            subsections=[
                SubSection(key=f"certifications.{i}", label=c, enabled=True)
                for i, c in enumerate(master_cv.certifications)
            ],
        ))

    return CVStructureResponse(master_cv_id=master_cv_id, sections=sections)
