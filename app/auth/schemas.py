import uuid
from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    # None for Google-OAuth users who haven't picked a username yet.
    username: str | None
    # BYO-LLM-keys feature: drives the one-time announcement popup and the
    # "fall back to app keys" preference. Carried on the client `user` object.
    has_seen_llm_keys_announcement: bool = False
    llm_fallback_to_shared: bool = False


class UserCreate(schemas.BaseUserCreate):
    username: str


class UserUpdate(schemas.BaseUserUpdate):
    username: str | None = None
    # User-settable preferences (safe self-owned flags).
    has_seen_llm_keys_announcement: bool | None = None
    llm_fallback_to_shared: bool | None = None
