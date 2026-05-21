from uuid import UUID
from app.db.base import AsyncSessionLocal

PLACEHOLDER_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
