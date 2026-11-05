"""A replica that restarts inside a rollup window does not double that window."""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
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
async def test_other_host_reuses_existing_row(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await stats_rollup.compute_rollup(db_session, WINDOW)
    monkeypatch.setattr(stats_rollup.socket, "gethostname", lambda: "replica-b")
    await stats_rollup.compute_rollup(db_session, WINDOW)
    assert await _rows(db_session) == 1
    assert await stats_rollup.duplicate_windows(db_session, WINDOW) == 0


@pytest.mark.asyncio
async def test_concurrent_hosts_write_one_rollup(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = os.environ.get("TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("TEST_POSTGRES_URL must point to a dedicated PostgreSQL test database")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    window = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(
        seconds=uuid.uuid4().int % (100 * 365 * 24 * 60 * 60)
    )
    ready = asyncio.Event()
    arrivals = 0

    async def run() -> DocumentStatsRollup:
        nonlocal arrivals
        async with sessions() as db:
            arrivals += 1
            if arrivals == 2:
                ready.set()
            await ready.wait()
            return await stats_rollup.compute_rollup(db, window)

    monkeypatch.setattr(
        stats_rollup.socket, "gethostname", lambda: asyncio.current_task().get_name()
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        first, second = await asyncio.gather(
            asyncio.create_task(run(), name="replica-a"),
            asyncio.create_task(run(), name="replica-b"),
        )
        async with sessions() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(DocumentStatsRollup)
                .where(DocumentStatsRollup.window_start == window)
            )
        assert count == 1
        assert first.id == second.id
    finally:
        async with sessions() as db:
            await db.execute(
                delete(DocumentStatsRollup).where(DocumentStatsRollup.window_start == window)
            )
            await db.commit()
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
