from pydantic import BaseModel


class GeneralATSScore(BaseModel):
    score: int
    strengths: list[str]
    improvements: list[str]


class JobATSScore(BaseModel):
    score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    improvements: list[str]
