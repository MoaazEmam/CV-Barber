from pydantic import BaseModel, Field, field_validator


def _coerce_score(v):
    """LLMs emit floats or numeric strings; coerce rather than fail. A truly
    missing score still fails (and retries) — a scoreless ATS result is useless."""
    if isinstance(v, str):
        v = v.strip()
    try:
        return round(float(v))
    except (TypeError, ValueError):
        return v


def _coerce_str_list(v):
    """null → [], bare string → [string], stringify items, drop nulls."""
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, list):
        return [str(x) for x in v if x is not None]
    return [str(v)]


class GeneralATSScore(BaseModel):
    score: int
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)

    _coerce_score = field_validator("score", mode="before")(_coerce_score)
    _coerce_lists = field_validator("strengths", "improvements", mode="before")(
        _coerce_str_list
    )


class JobATSScore(BaseModel):
    score: int
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)

    _coerce_score = field_validator("score", mode="before")(_coerce_score)
    _coerce_lists = field_validator(
        "matched_keywords", "missing_keywords", "improvements", mode="before"
    )(_coerce_str_list)

    # The prompt asks for the 3-6 most impactful missing keywords and prioritised
    # matches, but models sometimes dump every JD buzzword. Cap rather than fail —
    # the lists are ordered most-important-first.
    @field_validator("matched_keywords")
    @classmethod
    def _cap_matched(cls, v: list[str]) -> list[str]:
        return v[:15]

    @field_validator("missing_keywords")
    @classmethod
    def _cap_missing(cls, v: list[str]) -> list[str]:
        return v[:6]
