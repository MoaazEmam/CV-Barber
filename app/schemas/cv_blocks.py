from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class SectionType(str,Enum):
    EXPERIENCE = "experience"
    PROJECT = "project"
    EDUCATION = "education"
    SKILL = "skill"
    CERTIFICATION = "certification"

class DateRange(BaseModel):
    start: str = Field(description="e.g. 'Sep 2023' or '2022'")
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