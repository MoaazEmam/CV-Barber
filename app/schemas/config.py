from pydantic import BaseModel, Field

class TailoringConfig(BaseModel):
    top_n_experience: int = Field(default=3, ge=1, le=10)
    top_n_projects: int = Field(default=5, ge=1, le=10)
    output_format: str = Field(default="docx")
    include_summary: bool = Field(default=True)
    job_title: str = Field(description="Title of the role being applied for")
    company_name: str = Field(description="Company name for filename and cover letter")