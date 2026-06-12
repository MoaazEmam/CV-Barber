from pydantic import BaseModel, Field

class TailoringConfig(BaseModel):
    top_n_experience: int = Field(default=3, ge=1, le=50)
    top_n_projects: int = Field(default=5, ge=1, le=50)
    # Optional content rewrites. Experience/project reordering is always applied;
    # only the summary rewrite is opt-out. When False, the master summary is kept
    # verbatim. (Extend this group as more optional rewrites are added.)
    rewrite_summary: bool = Field(default=True)
    job_title: str = Field(description="Title of the role being applied for")
    company_name: str = Field(description="Company name for filename and cover letter")