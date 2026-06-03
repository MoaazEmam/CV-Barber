from typing import Optional
from pydantic import BaseModel, Field


class BaseCV(BaseModel):
    full_name:str
    # Optional: not every CV exposes an email; missing it shouldn't fail parsing.
    email:Optional[str]=None
    phone:Optional[str]=None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None