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
    company: str
    location: Optional[str] = None
    date_range: DateRange
    bullets: list[str] = Field(
        description="Each bullet is one accomplishment, no leading dash"
    )

class ProjectEntry(BaseModel):
    name: str
    description: str = Field(description="One sentence summary")
    tech_stack: list[str] = Field(description="e.g. ['Python', 'FastAPI', 'PostgreSQL']")
    bullets: list[str] = Field(
        description="What you built, what it does, results if any"
    )
    url: Optional[str] = None
    date_range: Optional[DateRange] = None

class EducationEntry(BaseModel):
    institution: str
    degree: str
    field: str
    date_range: DateRange
    gpa: Optional[str] = None
    relevant_courses: list[str] = Field(default_factory=list)

class SkillCategory(BaseModel):
    category: str = Field(description="e.g. 'Languages', 'Frameworks', 'Tools'")
    skills: list[str]