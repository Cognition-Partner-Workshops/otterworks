"""Folder-digest worker.

Every ``settings.folder_digest_interval_seconds`` the service lists the folders
that hold live documents, queues one job per folder, and a fixed number of
workers drain the queue: each job counts the folder's live documents, reads its
newest ``updated_at`` and upserts the result into ``folder_digests``. Jobs use
the same session factory, and so the same connection pool, as the API.

A cycle is scheduled on time whether or not the previous one drained, so when
jobs run slower than the interval the queue grows.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from opentelemetry import trace
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.document import Document, FolderDigest
from app.telemetry import (
    FOLDER_DIGEST_JOB_SECONDS,
    FOLDER_DIGEST_JOBS_TOTAL,
    FOLDER_DIGEST_OLDEST_JOB_AGE,
    FOLDER_DIGEST_QUEUE_DEPTH,
    db_source,
    is_statement_timeout,
)

logger = structlog.get_logger()
tracer = trace.get_tracer(__name__)

ERROR_CHARS = 200


@dataclass(frozen=True)
class DigestJob:
    folder_id: uuid.UUID
    enqueued_at: float


@dataclass(frozen=True)
class FolderStats:
    documents_total: int
    last_updated_at: datetime | None


async def list_folders(db: AsyncSession) -> list[uuid.UUID]:
    rows = await db.execute(
        select(Document.folder_id)
        .where(Document.folder_id.is_not(None), Document.is_deleted.is_(False))
        .distinct()
    )
    return [folder_id for (folder_id,) in rows.all()]


async def folder_stats(db: AsyncSession, folder_id: uuid.UUID) -> FolderStats:
    row = (
        await db.execute(
            select(func.count(), func.max(Document.updated_at)).where(
                Document.folder_id == folder_id, Document.is_deleted.is_(False)
            )
        )
    ).one()
    return FolderStats(documents_total=int(row[0]), last_updated_at=row[1])


async def upsert_digest(db: AsyncSession, folder_id: uuid.UUID, stats: FolderStats) -> None:
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    values = {
        "folder_id": folder_id,
        "documents_total": stats.documents_total,
        "last_updated_at": stats.last_updated_at,
        "computed_at": datetime.now(UTC),
    }
    stmt = insert(FolderDigest).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[FolderDigest.folder_id],
        set_={key: stmt.excluded[key] for key in values if key != "folder_id"},
    )
    await db.execute(stmt)
    await db.commit()


def _outcome(exc: BaseException) -> str:
    return "timeout" if is_statement_timeout(exc) else "error"


def _error_text(exc: BaseException) -> str:
    return " ".join(f"{type(exc).__name__}: {exc}".split())[:ERROR_CHARS]


class FolderDigestWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        interval_seconds: float,
        concurrency: int,
    ) -> None:
        self.session_factory = session_factory
        self.interval_seconds = interval_seconds
        self.concurrency = max(concurrency, 1)
        self.queue: asyncio.Queue[DigestJob] = asyncio.Queue()
        # Enqueue times of queued jobs, oldest first (the queue is FIFO).
        self._enqueued_at: deque[float] = deque()
        FOLDER_DIGEST_QUEUE_DEPTH.set_function(self.queue.qsize)
        FOLDER_DIGEST_OLDEST_JOB_AGE.set_function(self.oldest_job_age)

    def oldest_job_age(self) -> float:
        if not self._enqueued_at:
            return 0.0
        return max(time.monotonic() - self._enqueued_at[0], 0.0)

    def enqueue(self, folder_id: uuid.UUID) -> None:
        job = DigestJob(folder_id=folder_id, enqueued_at=time.monotonic())
        self._enqueued_at.append(job.enqueued_at)
        self.queue.put_nowait(job)

    async def _next_job(self) -> DigestJob:
        job = await self.queue.get()
        self._enqueued_at.popleft()
        return job

    async def run_cycle(self) -> int:
        """List folders and queue one job each; returns how many were queued."""
        token = db_source.set("worker")
        try:
            async with self.session_factory() as db:
                folders = await list_folders(db)
        except Exception as exc:
            logger.warning(
                "folder_digest_cycle_failed", outcome=_outcome(exc), error=_error_text(exc)
            )
            return 0
        finally:
            db_source.reset(token)
        for folder_id in folders:
            self.enqueue(folder_id)
        logger.info("folder_digest_cycle", folders=len(folders), queue_depth=self.queue.qsize())
        return len(folders)

    async def run_job(self, job: DigestJob) -> str:
        token = db_source.set("worker")
        started = time.perf_counter()
        outcome = "ok"
        try:
            with tracer.start_as_current_span("folder_digest.job") as span:
                span.set_attribute("folder.id", str(job.folder_id))
                try:
                    async with self.session_factory() as db:
                        stats = await folder_stats(db, job.folder_id)
                        await upsert_digest(db, job.folder_id, stats)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    outcome = _outcome(exc)
                    span.set_attribute("folder_digest.outcome", outcome)
                    logger.warning(
                        "folder_digest_job_failed",
                        folder_id=str(job.folder_id),
                        outcome=outcome,
                        error=_error_text(exc),
                    )
        finally:
            db_source.reset(token)
        FOLDER_DIGEST_JOB_SECONDS.observe(time.perf_counter() - started)
        FOLDER_DIGEST_JOBS_TOTAL.labels(outcome).inc()
        return outcome

    async def drain(self) -> None:
        while True:
            job = await self._next_job()
            try:
                await self.run_job(job)
            finally:
                self.queue.task_done()

    async def schedule(self) -> None:
        while True:
            started = time.monotonic()
            await self.run_cycle()
            await asyncio.sleep(max(self.interval_seconds - (time.monotonic() - started), 0))

    async def run(self) -> None:
        async with asyncio.TaskGroup() as group:
            group.create_task(self.schedule(), name="folder-digest-schedule")
            for n in range(self.concurrency):
                group.create_task(self.drain(), name=f"folder-digest-worker-{n}")


def start(session_factory: async_sessionmaker[AsyncSession]) -> asyncio.Task[None] | None:
    if not settings.folder_digest_enabled:
        return None
    worker = FolderDigestWorker(
        session_factory,
        interval_seconds=settings.folder_digest_interval_seconds,
        concurrency=settings.folder_digest_concurrency,
    )
    logger.info(
        "folder_digest_scheduled",
        interval_seconds=worker.interval_seconds,
        concurrency=worker.concurrency,
    )
    return asyncio.create_task(worker.run(), name="folder-digest")
