"""Shared test fixtures."""

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Uuid
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import documents as documents_api
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.middleware import request_log
from app.models.document import Comment, Document, DocumentVersion, Template  # noqa: F401
from tests.auth_helpers import TEST_JWT_SECRET, auth_headers

os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _store_uuids_as_postgres_renders_them() -> None:
    """SQLite has no uuid type and SQLAlchemy stores bare hex there.

    The metadata-filter repository compares owner_id as text, which matches on
    Postgres (hyphenated) but never on bare hex, so the tests store the
    hyphenated form too. Same approach as security/equivalence/harness.
    """

    def bind_processor(self, dialect):  # noqa: ANN001, ANN202 - SQLAlchemy hook
        def process(value):  # noqa: ANN001, ANN202
            return None if value is None else str(value)

        return process

    Uuid.bind_processor = bind_processor


_store_uuids_as_postgres_renders_them()

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


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


@pytest.fixture
def headers(owner_id: uuid.UUID) -> dict[str, str]:
    """Bearer token for the fixture owner; every document route needs a caller."""
    return auth_headers(owner_id)
