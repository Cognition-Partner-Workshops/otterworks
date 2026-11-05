"""A replica that restarts inside a rollup window does not double that window."""

import asyncio
import os
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.jobs import stats_rollup
from app.models.document import DocumentStatsRollup

WINDOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


async def _rows(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(DocumentStatsRollup))).scalar_one()


@pytest.mark.asyncio
async def test_same_host_rerun_reuses_its_row(db_session: AsyncSession) -> None:
    first = await stats_rollup.compute_rollup(db_session, WINDOW)
    again = await stats_rollup.compute_rollup(db_session, WINDOW)
    assert again.id == first.id
    assert await _rows(db_session) == 1


@pytest.mark.asyncio
async def test_concurrent_hosts_share_one_window_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.environ.get("TEST_ROLLUP_DATABASE_URL")
    if not url:
        pytest.skip("TEST_ROLLUP_DATABASE_URL must point to a disposable PostgreSQL database")
    schema = f"rollup_test_{uuid.uuid4().hex}"
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    host: ContextVar[str] = ContextVar("rollup_host")
    monkeypatch.setattr(stats_rollup.socket, "gethostname", host.get)
    ready = asyncio.Barrier(2)

    async def rollup(hostname: str) -> uuid.UUID:
        token = host.set(hostname)
        try:
            async with sessions() as db:
                await ready.wait()
                row = await stats_rollup.compute_rollup(db, WINDOW)
                return row.id
        finally:
            host.reset(token)

    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            await conn.run_sync(Base.metadata.create_all)
        rows = await asyncio.wait_for(
            asyncio.gather(rollup("replica-a"), rollup("replica-b")), timeout=10
        )
        async with sessions() as db:
            assert await _rows(db) == 1
            assert await stats_rollup.duplicate_windows(db, WINDOW) == 0
        assert rows[0] == rows[1]
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


@pytest.mark.asyncio
async def test_loop_survives_duplicate_check_failure_after_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A committed rollup whose duplicate check then fails must not stop the scheduler."""

    class Row:
        documents_total = 1
        versions_total = 1

    rollups = 0

    async def ok_rollup(db: object, window: object) -> Row:
        nonlocal rollups
        rollups += 1
        return Row()

    async def broken_duplicates(db: object, since: object) -> int:
        raise RuntimeError("connection reset")

    real_sleep = asyncio.sleep

    async def instant_sleep(delay: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(stats_rollup, "compute_rollup", ok_rollup)
    monkeypatch.setattr(stats_rollup, "duplicate_windows", broken_duplicates)
    monkeypatch.setattr(stats_rollup.asyncio, "sleep", instant_sleep)
    task = asyncio.create_task(stats_rollup.loop(async_sessionmaker()))
    for _ in range(40):
        await real_sleep(0)
    assert not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert rollups > 1
