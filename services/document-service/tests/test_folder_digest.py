"""The folder-digest worker queues one job per folder and keeps going under DB trouble."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from asyncpg.exceptions import QueryCanceledError
from prometheus_client import REGISTRY
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.base import Base
from app.jobs import folder_digest
from app.models.document import Document, FolderDigest
from tests.conftest import TestingSessionLocal

OWNER = uuid.UUID("6d0c5f5e-7f0f-4a4e-9d0c-1a1c1d3a7001")


def _sample(name: str, labels: dict[str, str] | None = None) -> float:
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


def _timeout_error() -> DBAPIError:
    cause = QueryCanceledError("canceling statement due to statement timeout")
    try:
        try:
            raise cause
        except QueryCanceledError as exc:
            raise RuntimeError("asyncpg adapter error") from exc
    except RuntimeError as wrapped:
        return DBAPIError("SELECT count(*) FROM documents", {}, wrapped)


async def _seed(db: AsyncSession, folders: dict[uuid.UUID | None, int]) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for folder_id, count in folders.items():
        for i in range(count):
            db.add(
                Document(
                    title=f"doc {i}",
                    owner_id=OWNER,
                    folder_id=folder_id,
                    updated_at=base + timedelta(minutes=i),
                )
            )
    await db.commit()


def _worker(interval: float = 60, concurrency: int = 2) -> folder_digest.FolderDigestWorker:
    return folder_digest.FolderDigestWorker(TestingSessionLocal, interval, concurrency)


def test_settings_default_off() -> None:
    fresh = Settings(_env_file=None)
    assert fresh.folder_digest_enabled is False
    assert fresh.folder_digest_interval_seconds == 15
    assert fresh.folder_digest_concurrency == 4
    assert fresh.db_statement_timeout_ms == 0


def test_start_is_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(folder_digest.settings, "folder_digest_enabled", False)
    assert folder_digest.start(TestingSessionLocal) is None


@pytest.mark.asyncio
async def test_cycle_enqueues_one_job_per_live_folder(db_session: AsyncSession) -> None:
    a, b, gone = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await _seed(db_session, {a: 3, b: 1, None: 2})
    db_session.add(Document(title="deleted", owner_id=OWNER, folder_id=gone, is_deleted=True))
    await db_session.commit()

    worker = _worker()
    queued = await worker.run_cycle()

    assert queued == 2
    assert worker.queue.qsize() == 2
    assert _sample("otterworks_folder_digest_queue_depth") == 2
    jobs = {worker.queue.get_nowait().folder_id for _ in range(2)}
    assert jobs == {a, b}


@pytest.mark.asyncio
async def test_job_upserts_count_and_newest_update(db_session: AsyncSession) -> None:
    folder = uuid.uuid4()
    await _seed(db_session, {folder: 3})
    worker = _worker()
    ok_before = _sample("otterworks_folder_digest_jobs_total", {"outcome": "ok"})

    worker.enqueue(folder)
    assert await worker.run_job(await worker._next_job()) == "ok"
    db_session.add(Document(title="late", owner_id=OWNER, folder_id=folder))
    await db_session.commit()
    worker.enqueue(folder)
    assert await worker.run_job(await worker._next_job()) == "ok"

    db_session.expire_all()
    rows = (await db_session.execute(select(FolderDigest))).scalars().all()
    assert len(rows) == 1
    assert rows[0].folder_id == folder
    assert rows[0].documents_total == 4
    assert rows[0].last_updated_at is not None
    assert _sample("otterworks_folder_digest_jobs_total", {"outcome": "ok"}) == ok_before + 2
    assert _sample("otterworks_folder_digest_job_duration_seconds_count") >= 2


@pytest.mark.asyncio
async def test_drain_empties_the_queue(tmp_path) -> None:
    # TestingSessionLocal's in-memory engine is one shared connection, so
    # concurrent sessions interleave a single transaction and a closing
    # session's rollback can drop another's pending insert. A file-backed
    # database gives each session its own connection, like production.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/drain.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    folders = [uuid.uuid4() for _ in range(5)]
    async with factory() as db:
        await _seed(db, dict.fromkeys(folders, 2))

    worker = folder_digest.FolderDigestWorker(factory, 60, 3)
    await worker.run_cycle()

    drains = [asyncio.create_task(worker.drain()) for _ in range(worker.concurrency)]
    await asyncio.wait_for(worker.queue.join(), timeout=5)
    for task in drains:
        task.cancel()
    await asyncio.gather(*drains, return_exceptions=True)

    assert worker.queue.qsize() == 0
    assert worker.oldest_job_age() == 0.0
    async with factory() as db:
        rows = (await db.execute(select(FolderDigest))).scalars().all()
    assert {row.folder_id for row in rows} == set(folders)
    await engine.dispose()


@pytest.mark.asyncio
async def test_statement_timeout_is_counted_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    async def timed_out(db: AsyncSession, folder_id: uuid.UUID) -> None:
        raise _timeout_error()

    async def broken(db: AsyncSession, folder_id: uuid.UUID) -> None:
        raise RuntimeError("connection reset")

    worker = _worker()
    timeouts = _sample("otterworks_folder_digest_jobs_total", {"outcome": "timeout"})
    errors = _sample("otterworks_folder_digest_jobs_total", {"outcome": "error"})

    monkeypatch.setattr(folder_digest, "folder_stats", timed_out)
    worker.enqueue(uuid.uuid4())
    assert await worker.run_job(await worker._next_job()) == "timeout"
    monkeypatch.setattr(folder_digest, "folder_stats", broken)
    worker.enqueue(uuid.uuid4())
    assert await worker.run_job(await worker._next_job()) == "error"

    assert _sample("otterworks_folder_digest_jobs_total", {"outcome": "timeout"}) == timeouts + 1
    assert _sample("otterworks_folder_digest_jobs_total", {"outcome": "error"}) == errors + 1


@pytest.mark.asyncio
async def test_failed_cycle_query_does_not_stop_the_schedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def flaky(db: AsyncSession) -> list[uuid.UUID]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _timeout_error()
        return [uuid.uuid4()]

    monkeypatch.setattr(folder_digest, "list_folders", flaky)
    worker = _worker(interval=0.01)
    task = asyncio.create_task(worker.schedule())
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls > 2
    assert worker.queue.qsize() == calls - 1


@pytest.mark.asyncio
async def test_backlog_grows_when_jobs_are_slower_than_the_interval(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed(db_session, {uuid.uuid4(): 1 for _ in range(10)})

    async def slow_stats(db: AsyncSession, folder_id: uuid.UUID) -> None:
        await asyncio.sleep(0.2)
        raise _timeout_error()

    monkeypatch.setattr(folder_digest, "folder_stats", slow_stats)
    worker = _worker(interval=0.05, concurrency=2)
    task = asyncio.create_task(worker.run())
    depths = []
    for _ in range(4):
        await asyncio.sleep(0.12)
        depths.append(_sample("otterworks_folder_digest_queue_depth"))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert depths == sorted(depths)
    assert depths[-1] > depths[0] > 0
    assert worker.oldest_job_age() > 0.2
    assert _sample("otterworks_folder_digest_oldest_job_age_seconds") > 0.2


@pytest.mark.asyncio
async def test_cancel_stops_schedule_and_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(folder_digest.settings, "folder_digest_enabled", True)
    monkeypatch.setattr(folder_digest.settings, "folder_digest_interval_seconds", 1)
    task = folder_digest.start(TestingSessionLocal)
    assert task is not None
    await asyncio.sleep(0.05)
    before = {t for t in asyncio.all_tasks() if t.get_name().startswith("folder-digest")}
    assert len(before) == 2 + folder_digest.settings.folder_digest_concurrency

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert all(t.done() for t in before)
