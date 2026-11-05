"""Scheduled document-stats rollup.

Every ``settings.rollup_interval_seconds`` the service snapshots document,
version and word totals into ``document_stats_rollups`` for the usage
dashboard. The schedule is aligned to wall-clock windows so restarts do not
shift the series.
"""

from __future__ import annotations

import asyncio
import socket
import time
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.document import Document, DocumentStatsRollup, DocumentVersion
from app.telemetry import ROLLUP_DUPLICATE_WINDOWS, ROLLUP_RUNS_TOTAL, SERVICE

logger = structlog.get_logger()

# Re-read the duplicate-window gauge this long after the rollup, so a duplicate
# committed by another replica after this process's own rollup is still reported
# from this process's /metrics.
DUPLICATE_RECHECK_DELAY_SECONDS = 10
ROLLUP_LOCK_ID = 0x4F57524F4C4C5550


def current_window(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    interval = settings.rollup_interval_seconds
    epoch = int(now.timestamp())
    return datetime.fromtimestamp(epoch - epoch % interval, tz=UTC)


async def compute_rollup(db: AsyncSession, window_start: datetime) -> DocumentStatsRollup | None:
    # Hold coordination through the commit; a waiting replica must check again
    # after the winner's row becomes visible (PostgreSQL READ COMMITTED).
    await db.execute(select(func.pg_advisory_xact_lock(ROLLUP_LOCK_ID)))
    existing = await db.execute(
        select(DocumentStatsRollup.id)
        .where(DocumentStatsRollup.window_start == window_start)
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        await db.commit()
        return None

    live = Document.is_deleted.is_(False)
    documents_total = (
        await db.execute(select(func.count()).select_from(Document).where(live))
    ).scalar_one()
    words_total = (
        await db.execute(select(func.coalesce(func.sum(Document.word_count), 0)).where(live))
    ).scalar_one()
    versions_total = (
        await db.execute(select(func.count()).select_from(DocumentVersion))
    ).scalar_one()

    row = DocumentStatsRollup(
        window_start=window_start,
        documents_total=documents_total,
        versions_total=versions_total,
        words_total=int(words_total),
        computed_by=socket.gethostname(),
    )
    db.add(row)
    await db.commit()
    return row


async def duplicate_windows(db: AsyncSession, since: datetime) -> int:
    dupes = (
        select(DocumentStatsRollup.window_start)
        .where(DocumentStatsRollup.window_start >= since)
        .group_by(DocumentStatsRollup.window_start)
        .having(func.count() > 1)
    ).subquery()
    return (await db.execute(select(func.count()).select_from(dupes))).scalar_one()


async def refresh_duplicate_gauge(
    session_factory: async_sessionmaker[AsyncSession], window: datetime
) -> int:
    async with session_factory() as db:
        dupes = await duplicate_windows(db, window - timedelta(hours=1))
    ROLLUP_DUPLICATE_WINDOWS.labels(SERVICE).set(dupes)
    return dupes


async def run_once(session_factory: async_sessionmaker[AsyncSession]) -> None:
    window = current_window()
    async with session_factory() as db:
        try:
            row = await compute_rollup(db, window)
        except Exception:
            ROLLUP_RUNS_TOTAL.labels(SERVICE, "error").inc()
            logger.exception("stats_rollup_failed", window_start=window.isoformat())
            return
        if row is None:
            ROLLUP_RUNS_TOTAL.labels(SERVICE, "skipped").inc()
            logger.info("stats_rollup_skipped", window_start=window.isoformat())
        else:
            ROLLUP_RUNS_TOTAL.labels(SERVICE, "success").inc()
            logger.info(
                "stats_rollup_completed",
                window_start=window.isoformat(),
                documents_total=row.documents_total,
                versions_total=row.versions_total,
            )
    await refresh_duplicate_gauge(session_factory, window)


async def loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    interval = settings.rollup_interval_seconds
    while True:
        # Fire a couple of seconds into each window so every replica lands in
        # the same window regardless of how the loop was started.
        delay = interval - (time.time() % interval) + 2
        await asyncio.sleep(delay)
        window = current_window()
        # The rollup itself commits inside run_once; nothing after that point
        # (the duplicate-window gauge is reporting only) may take the
        # scheduler down and stop future windows.
        try:
            await run_once(session_factory)
            await asyncio.sleep(DUPLICATE_RECHECK_DELAY_SECONDS)
            await refresh_duplicate_gauge(session_factory, window)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("stats_rollup_iteration_failed", window_start=window.isoformat())


def start(session_factory: async_sessionmaker[AsyncSession]) -> asyncio.Task[None] | None:
    if not settings.rollup_enabled:
        return None
    logger.info("stats_rollup_scheduled", interval_seconds=settings.rollup_interval_seconds)
    return asyncio.create_task(loop(session_factory), name="stats-rollup")
