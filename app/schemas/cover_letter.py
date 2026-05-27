from pydantic import BaseModel


class CoverLetterResponse(BaseModel):
    cover_letter: str
