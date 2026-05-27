from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_master_cv
from app.api.models import CVStructureResponse, Section, SubSection
from app.auth.config import current_active_user
from app.db.dependencies import get_db
from app.db.models import User, MasterCVModel, ApplicationModel
from sqlalchemy import select

router = APIRouter()


def _sections_from_cv(cv) -> list[Section]:
    """Build a section tree from any CV-like object (MasterCV or TailoredCV)."""
    sections: list[Section] = []

    if getattr(cv, "experience", None):
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
                for i, e in enumerate(cv.experience)
            ],
        ))

    if getattr(cv, "projects", None):
        sections.append(Section(
            key="projects",
            label="Projects",
            enabled=True,
            subsections=[
                SubSection(key=f"projects.{i}", label=p.name, enabled=True)
                for i, p in enumerate(cv.projects)
            ],
        ))

    if getattr(cv, "skills", None):
        sections.append(Section(
            key="skills",
            label="Skills",
            enabled=True,
            subsections=[
                SubSection(key=f"skills.{i}", label=s.category, enabled=True)
                for i, s in enumerate(cv.skills)
            ],
        ))

    if getattr(cv, "education", None):
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
                for i, ed in enumerate(cv.education)
            ],
        ))

    if getattr(cv, "certifications", None):
        sections.append(Section(
            key="certifications",
            label="Certifications",
            enabled=True,
            subsections=[
                SubSection(key=f"certifications.{i}", label=c, enabled=True)
                for i, c in enumerate(cv.certifications)
            ],
        ))

    return sections


@router.get("/cv/structure/{master_cv_id}", response_model=CVStructureResponse)
async def get_cv_structure(
    master_cv_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Returns section structure for a master CV (all uploaded entries)."""
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

    return CVStructureResponse(
        master_cv_id=master_cv_id,
        sections=_sections_from_cv(master_cv),
    )


@router.get("/applications/{application_id}/structure", response_model=CVStructureResponse)
async def get_application_structure(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    """Returns section structure built from the TAILORED CV stored in the application.

    This is what SectionEditor must use — indices here match exactly what
    apply_section_config iterates over, so toggling entry N disables the
    correct entry in the downloaded/previewed CV.
    """
    result = await db.execute(
        select(ApplicationModel).where(ApplicationModel.id == application_id)
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    from app.schemas.tailored_cv import TailoredCV
    tailored_cv = TailoredCV.model_validate(application.tailored_cv_data)

    return CVStructureResponse(
        master_cv_id=application.master_cv_id,
        sections=_sections_from_cv(tailored_cv),
    )
