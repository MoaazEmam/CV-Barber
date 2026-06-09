from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum

class SectionType(str,Enum):
    EXPERIENCE = "experience"
    PROJECT = "project"
    EDUCATION = "education"
    SKILL = "skill"
    CERTIFICATION = "certification"

class DateRange(BaseModel):
    # Optional: dateless entries (e.g. personal/course projects) are common, and
    # the LLM often emits date_range={"start": null}. Tolerate it rather than
    # failing the whole parse. Matches the documented "dateless entries validate".
    start: Optional[str] = Field(
        default=None, description="e.g. 'Sep 2023' or '2022'"
    )
    end: Optional[str] = Field(
        default=None,
        description="None means present/current"
    )

class ExperienceEntry(BaseModel):
    title: str = Field(description="Job title")
    company: Optional[str]=None
    location: Optional[str] = None
    date_range: DateRange
    # Optional: prose/paragraph CVs may have no bullets, or keep prose as one bullet.
    bullets: list[str] = Field(
        default_factory=list,
        description="Each bullet is one accomplishment, no leading dash",
    )

class ProjectEntry(BaseModel):
    name: str
    description: Optional[str] = None
    tech_stack: list[str] = Field(
        default_factory=list, description="e.g. ['Python', 'FastAPI', 'PostgreSQL']"
    )
    bullets: list[str] = Field(
        default_factory=list,
        description="What you built, what it does, results if any",
    )
    url: Optional[str] = None
    date_range: Optional[DateRange] = None

class EducationEntry(BaseModel):
    institution: str
    degree: Optional[str]=None
    faculty: Optional[str]=None
    # Optional: bootcamps / high-school / certificate programs often have no field.
    field: Optional[str] = None
    minor: Optional[str] = None
    honors: Optional[str] = None
    date_range: DateRange
    gpa: Optional[str] = None
    relevant_courses: list[str] = Field(default_factory=list)

class SkillCategory(BaseModel):
    category: str = Field(description="e.g. 'Languages', 'Frameworks', 'Tools'")
    skills: list[str]


class AdditionalEntry(BaseModel):
    """A flexible row inside a non-standard section (an award, a language, a
    leadership role…). Every field is optional so any block shape round-trips.

    Validators coerce the loose shapes LLMs emit (a bullet as a bare string, a
    detail as a list) so best-effort preservation never fails the whole parse."""
    heading: Optional[str] = Field(default=None, description="the item's main label/title")
    subheading: Optional[str] = Field(
        default=None, description="org, qualifier, or a right-aligned tag e.g. 'First Place (2022)'"
    )
    location: Optional[str] = None
    date_range: Optional[DateRange] = None
    bullets: list[str] = Field(default_factory=list)
    detail: Optional[str] = Field(
        default=None, description="free text when the block isn't entry-shaped, e.g. a Languages line"
    )

    @field_validator("bullets", mode="before")
    @classmethod
    def _coerce_bullets(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        return [str(v)]

    @field_validator("detail", mode="before")
    @classmethod
    def _coerce_detail(cls, v):
        if isinstance(v, list):
            return "; ".join(str(x) for x in v if x is not None)
        return v


class AdditionalSection(BaseModel):
    """Any CV section the structured schema does not model explicitly (Honors &
    Awards, Languages, Leadership & Community, standalone Coursework, Volunteering,
    Training…), preserved verbatim so a template that supports it can render it."""
    title: str = Field(description="the section heading exactly as written")
    entries: list[AdditionalEntry] = Field(default_factory=list)

    @field_validator("entries", mode="before")
    @classmethod
    def _coerce_entries(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            v = [v]
        if not isinstance(v, list):
            return []
        out = []
        for e in v:
            if isinstance(e, str):
                out.append({"detail": e})
            elif isinstance(e, dict):
                out.append(e)
        return out


def coerce_additional_sections(v):
    """Normalise the ``additional_sections`` value an LLM emits into a clean list of
    section dicts. A dict (``{title: entries}``) becomes a list; non-dict / titleless
    items are dropped. Tolerant by design — these sections are best-effort extras."""
    if v is None:
        return []
    if isinstance(v, dict):
        return [{"title": k, "entries": val} for k, val in v.items()]
    if not isinstance(v, list):
        return []
    return [s for s in v if isinstance(s, dict) and s.get("title")]