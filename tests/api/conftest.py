"""HTTP-level fixtures: an in-process ASGI client wired to the test DB session,
plus real JWT access tokens so auth/superuser gating is exercised for real."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.auth.config import get_jwt_strategy
from app.db.dependencies import get_db


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


async def _auth_headers(user) -> dict:
    token = await get_jwt_strategy().write_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_headers(test_user):
    return await _auth_headers(test_user)


@pytest_asyncio.fixture
async def admin_headers(superuser):
    return await _auth_headers(superuser)
