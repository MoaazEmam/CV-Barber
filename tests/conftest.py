import uuid

import pytest
import pytest_asyncio
from fastapi_users.password import PasswordHelper
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.db.models import User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# The models use Postgres JSONB; SQLite (test DB) has no JSONB type. Render it as
# JSON so Base.metadata.create_all works against SQLite — test-only, production
# still uses real JSONB.
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # noqa: ANN001
    return "JSON"


# Postgres UUID compiles to a bare "UUID" DDL type on SQLite, which gets NUMERIC
# affinity — an all-digit UUID then round-trips back as an int and breaks the
# result processor. CHAR(32) gives TEXT affinity so the hex value stays a string.
@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(element, compiler, **kw):  # noqa: ANN001
    return "CHAR(32)"


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


@pytest_asyncio.fixture
async def superuser(db_session):
    password_helper = PasswordHelper()
    user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        email="admin@cvbarber.dev",
        username="adminuser",
        hashed_password=password_helper.hash("adminpassword"),
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user
