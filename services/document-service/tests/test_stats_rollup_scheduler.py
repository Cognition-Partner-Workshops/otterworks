"""Scheduling and bookkeeping around the document-stats rollup."""

import asyncio
from datetime import UTC, datetime

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import func, select

from app.config import settings
from app.jobs import stats_rollup
from app.models.document import DocumentStatsRollup
from app.telemetry import SERVICE
from tests.conftest import TestingSessionLocal


def _runs(outcome: str) -> float:
    value = REGISTRY.get_sample_value(
        "otterworks_rollup_runs_total", {"service": SERVICE, "outcome": outcome}
    )
    return value or 0.0


def _duplicates_gauge() -> float | None:
    return REGISTRY.get_sample_value("otterworks_rollup_duplicate_windows", {"service": SERVICE})


def test_current_window_aligns_to_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rollup_interval_seconds", 60)
    now = datetime(2026, 1, 1, 12, 3, 41, tzinfo=UTC)
    assert stats_rollup.current_window(now) == datetime(2026, 1, 1, 12, 3, tzinfo=UTC)


@pytest.mark.asyncio
async def test_run_once_records_success_and_refreshes_duplicate_gauge() -> None:
    before = _runs("success")

    await stats_rollup.run_once(TestingSessionLocal)

    assert _runs("success") == before + 1
    assert _duplicates_gauge() == 0
    async with TestingSessionLocal() as db:
        count = (
            await db.execute(select(func.count()).select_from(DocumentStatsRollup))
        ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_run_once_records_error_and_skips_gauge(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_rollup(db: object, window: object) -> None:
        raise RuntimeError("db down")

    async def unexpected_refresh(*_args: object) -> int:
        raise AssertionError("gauge must not refresh after a failed rollup")

    monkeypatch.setattr(stats_rollup, "compute_rollup", failing_rollup)
    monkeypatch.setattr(stats_rollup, "refresh_duplicate_gauge", unexpected_refresh)
    before = _runs("error")

    await stats_rollup.run_once(TestingSessionLocal)

    assert _runs("error") == before + 1


@pytest.mark.asyncio
async def test_loop_keeps_running_when_an_iteration_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    async def failing_run_once(factory: object) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("transient")

    real_sleep = asyncio.sleep

    async def instant_sleep(delay: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(stats_rollup, "run_once", failing_run_once)
    monkeypatch.setattr(stats_rollup.asyncio, "sleep", instant_sleep)
    task = asyncio.create_task(stats_rollup.loop(TestingSessionLocal))
    for _ in range(20):
        await real_sleep(0)
    assert not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert attempts > 1


def test_start_is_a_no_op_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rollup_enabled", False)
    assert stats_rollup.start(TestingSessionLocal) is None


@pytest.mark.asyncio
async def test_start_schedules_the_loop_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()

    async def fake_loop(factory: object) -> None:
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(settings, "rollup_enabled", True)
    monkeypatch.setattr(stats_rollup, "loop", fake_loop)

    task = stats_rollup.start(TestingSessionLocal)
    assert task is not None
    assert task.get_name() == "stats-rollup"
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_loop_rechecks_duplicates_after_a_successful_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = 0
    rechecks: list[datetime] = []
    sleeps: list[float] = []

    async def ok_run_once(factory: object) -> None:
        nonlocal runs
        runs += 1

    async def record_refresh(factory: object, window: datetime) -> int:
        rechecks.append(window)
        return 0

    real_sleep = asyncio.sleep

    async def instant_sleep(delay: float) -> None:
        sleeps.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(stats_rollup, "run_once", ok_run_once)
    monkeypatch.setattr(stats_rollup, "refresh_duplicate_gauge", record_refresh)
    monkeypatch.setattr(stats_rollup.asyncio, "sleep", instant_sleep)
    task = asyncio.create_task(stats_rollup.loop(TestingSessionLocal))
    for _ in range(20):
        await real_sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert runs >= 1
    assert len(rechecks) >= 1
    assert stats_rollup.DUPLICATE_RECHECK_DELAY_SECONDS in sleeps
