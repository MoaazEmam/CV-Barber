import uuid

import pytest
import pytest_asyncio
from fastapi_users.password import PasswordHelper
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.db.models import User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_user(db_session):
    password_helper = PasswordHelper()
    user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        email="test@cvbarber.dev",
        username="testuser",
        hashed_password=password_helper.hash("testpassword"),
        is_active=True,
        is_superuser=False,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user
