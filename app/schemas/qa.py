from pydantic import BaseModel


class QARequest(BaseModel):
    questions: list[str]


class QAItem(BaseModel):
    question: str
    answer: str


class QAResponse(BaseModel):
    answers: list[QAItem]
