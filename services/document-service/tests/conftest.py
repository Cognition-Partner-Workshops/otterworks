"""Shared test fixtures."""

import os
import uuid
from collections.abc import AsyncGenerator

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Uuid
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-pad32"  # noqa: S105
os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("SHARE_LINK_SECRET", "test-share-link-secret")

from app.api import documents as documents_api  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware import request_log  # noqa: E402
from app.models.document import Comment, Document, DocumentVersion, Template  # noqa: E402, F401


def auth_headers(user_id: uuid.UUID | str) -> dict[str, str]:
    token = jwt.encode({"user_id": str(user_id)}, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _store_uuids_hyphenated(self, dialect):  # noqa: ANN001, ANN202 - SQLAlchemy hook
    """Store uuids the way Postgres renders them, so raw owner_id SQL matches on SQLite."""

    def process(value):  # noqa: ANN001, ANN202
        return None if value is None else str(value)

    return process


Uuid.bind_processor = _store_uuids_hyphenated

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
def chaos_flags_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never observe a developer's local Redis: every chaos flag reads as off."""
    monkeypatch.setattr(documents_api, "flag_active", lambda key: False)
    monkeypatch.setattr(request_log, "flag_active", lambda key: False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def owner_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def folder_id() -> uuid.UUID:
    return uuid.uuid4()
