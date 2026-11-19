"""Application startup/shutdown, DB session helpers and health degradation."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app import main
from app.db import session as session_module
from app.db.session import get_db
from tests.conftest import engine as test_engine


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeTask:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


@pytest.mark.asyncio
async def test_lifespan_migrates_starts_rollup_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = FakeEngine()
    task = FakeTask()
    migrated: list[object] = []
    started: list[object] = []

    async def fake_upgrade(engine: object) -> None:
        migrated.append(engine)

    def fake_start(factory: object) -> FakeTask:
        started.append(factory)
        return task

    monkeypatch.setattr(main, "engine", fake_engine)
    monkeypatch.setattr(main, "upgrade_to_head", fake_upgrade)
    monkeypatch.setattr(main.stats_rollup, "start", fake_start)

    async with main.lifespan(main.app):
        assert migrated == [fake_engine]
        assert started == [main.async_session]
        assert not task.cancelled
        assert not fake_engine.disposed

    assert task.cancelled
    assert fake_engine.disposed


@pytest.mark.asyncio
async def test_lifespan_without_rollup_task(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_engine = FakeEngine()

    async def fake_upgrade(engine: object) -> None:
        return None

    monkeypatch.setattr(main, "engine", fake_engine)
    monkeypatch.setattr(main, "upgrade_to_head", fake_upgrade)
    monkeypatch.setattr(main.stats_rollup, "start", lambda factory: None)

    async with main.lifespan(main.app):
        pass

    assert fake_engine.disposed


def test_routers_are_mounted() -> None:
    paths = {getattr(route, "path", None) for route in main.app.routes}
    assert {
        "/health",
        "/metrics",
        "/api/v1/documents/",
        "/api/v1/documents/{document_id}/comments",
        "/api/v1/templates/",
    } <= paths


@pytest.mark.asyncio
async def test_get_db_yields_and_closes_a_session(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []
    real_close = AsyncSession.close

    async def tracking_close(self: AsyncSession) -> None:
        closed.append(True)
        await real_close(self)

    monkeypatch.setattr(AsyncSession, "close", tracking_close)
    gen = get_db()
    session = await gen.__anext__()
    assert isinstance(session, AsyncSession)
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()
    assert closed


@pytest.mark.asyncio
async def test_init_db_creates_all_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: session_module.Base.metadata.drop_all(sync_conn))
    monkeypatch.setattr(session_module, "engine", test_engine)

    await session_module.init_db()

    async with test_engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
    assert {"documents", "document_versions", "comments", "templates"} <= set(tables)


class BrokenSession:
    async def execute(self, *_args, **_kwargs):
        raise ConnectionError("database unreachable")


@pytest.mark.asyncio
async def test_health_reports_degraded_when_database_is_down() -> None:
    async def broken_db() -> AsyncGenerator[BrokenSession, None]:
        yield BrokenSession()

    main.app.dependency_overrides[get_db] = broken_db
    try:
        transport = ASGITransport(app=main.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/health")
    finally:
        main.app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "degraded",
        "service": "document-service",
        "checks": {"database": "disconnected"},
    }
