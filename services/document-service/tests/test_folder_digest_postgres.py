"""Against a real PostgreSQL, slow digest jobs back the queue up and time out.

Run with DOC_SVC_TEST_POSTGRES_URL pointing at a migrated database. Each job's
upsert waits on a lock held by another connection until the per-connection
statement_timeout cancels it, so every job is slower than the cycle interval.
"""

import asyncio
import os
import uuid

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import telemetry
from app.db.session import engine_connect_args
from app.jobs import folder_digest

POSTGRES_URL = os.environ.get("DOC_SVC_TEST_POSTGRES_URL")
OWNER = uuid.UUID("6d0c5f5e-7f0f-4a4e-9d0c-1a1c1d3a7002")
FOLDERS = 40
POOL_SIZE = 4

pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="DOC_SVC_TEST_POSTGRES_URL not set")


def _sample(name: str, labels: dict[str, str] | None = None) -> float:
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


@pytest.mark.asyncio
async def test_queue_depth_grows_under_statement_timeout() -> None:
    assert POSTGRES_URL
    admin = create_async_engine(POSTGRES_URL)
    engine = create_async_engine(
        POSTGRES_URL,
        pool_size=POOL_SIZE,
        max_overflow=0,
        connect_args=engine_connect_args(100),
    )
    telemetry.instrument_statement_timeouts()
    telemetry.instrument_pool(engine, POOL_SIZE, 0)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with admin.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO documents (id, title, owner_id, folder_id) "
                "SELECT gen_random_uuid(), 'pg digest ' || g, :owner, f.id "
                "FROM generate_series(1, :n) g "
                "JOIN (SELECT n, gen_random_uuid() AS id FROM generate_series(1, :folders) n) f "
                "ON f.n = 1 + g % :folders"
            ),
            {"owner": OWNER, "n": FOLDERS * 5, "folders": FOLDERS},
        )

    worker_timeouts = _sample("otterworks_db_statement_timeouts_total", {"source": "worker"})
    job_timeouts = _sample("otterworks_folder_digest_jobs_total", {"outcome": "timeout"})
    lock = await admin.connect()
    task: asyncio.Task[None] | None = None
    try:
        await lock.execute(text("BEGIN"))
        await lock.execute(text("LOCK TABLE folder_digests IN ACCESS EXCLUSIVE MODE"))

        worker = folder_digest.FolderDigestWorker(factory, interval_seconds=0.3, concurrency=4)
        task = asyncio.create_task(worker.run())
        depths, checked_out = [], []
        for _ in range(5):
            await asyncio.sleep(0.4)
            depths.append(_sample("otterworks_folder_digest_queue_depth"))
            checked_out.append(_sample("otterworks_db_pool_checked_out"))
        print(f"queue_depth samples={depths} pool_checked_out samples={checked_out}")
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await lock.rollback()
        await lock.close()
        async with admin.begin() as conn:
            await conn.execute(text("DELETE FROM documents WHERE owner_id = :o"), {"o": OWNER})
        await engine.dispose()
        await admin.dispose()

    assert depths == sorted(depths)
    assert depths[-1] > depths[0] >= FOLDERS
    assert max(checked_out) == POOL_SIZE
    assert _sample("otterworks_db_pool_capacity") == POOL_SIZE
    assert _sample("otterworks_db_statement_timeouts_total", {"source": "worker"}) > worker_timeouts
    assert _sample("otterworks_folder_digest_jobs_total", {"outcome": "timeout"}) > job_timeouts
