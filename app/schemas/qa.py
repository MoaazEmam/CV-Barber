from pydantic import BaseModel, Field, field_validator


class QARequest(BaseModel):
    questions: list[str] = Field(..., min_length=1, max_length=10)

    @field_validator("questions")
    @classmethod
    def _check_question_length(cls, v: list[str]) -> list[str]:
        # Generous upper bound — real questions (even long essay-style prompts)
        # are well under this; it only blocks abusive multi-KB payloads.
        for q in v:
            if len(q) > 5000:
                raise ValueError("Each question must be at most 5000 characters.")
        return v


class QAItem(BaseModel):
    question: str
    # Required — an empty answer should fail and retry — but tolerate the LLM
    # returning an answer as a list of parts.
    answer: str

    @field_validator("answer", mode="before")
    @classmethod
    def _coerce_answer(cls, v):
        if isinstance(v, list):
            return "; ".join(str(x) for x in v if x is not None)
        return v


class QAResponse(BaseModel):
    answers: list[QAItem]
