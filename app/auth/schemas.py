import uuid
from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    # None for Google-OAuth users who haven't picked a username yet.
    username: str | None


class UserCreate(schemas.BaseUserCreate):
    username: str


class UserUpdate(schemas.BaseUserUpdate):
    username: str | None = None
