from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.schemas.cv_blocks import Link, coerce_links


class BaseCV(BaseModel):
    # full_name is the one genuinely vital field — fail early with a clear
    # message instead of letting an empty string slip through.
    full_name:str

    @field_validator("full_name", mode="before")
    @classmethod
    def _require_full_name(cls, v):
        if not v or not str(v).strip():
            raise ValueError("full_name is required and cannot be empty")
        return str(v).strip()
    # Optional: not every CV exposes an email; missing it shouldn't fail parsing.
    email:Optional[str]=None
    phone:Optional[str]=None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None
    # Any other profile/contact link (Portfolio, Twitter/X, Google Scholar, ORCID,
    # StackOverflow, …) that has no dedicated field — preserved so nothing is lost.
    links: list[Link] = Field(default_factory=list)

    @field_validator("links", mode="before")
    @classmethod
    def _coerce_links(cls, v):
        return coerce_links(v)