"""Settings, statement timeouts and pool gauges for the shared database engine."""

import json

import pytest
from asyncpg.exceptions import QueryCanceledError
from httpx import AsyncClient
from prometheus_client import REGISTRY
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app import telemetry
from app.config import Settings
from app.db.session import engine_connect_args

NEW_METRICS = (
    "otterworks_folder_digest_queue_depth",
    "otterworks_folder_digest_oldest_job_age_seconds",
    "otterworks_folder_digest_jobs_total",
    "otterworks_folder_digest_job_duration_seconds",
    "otterworks_db_pool_checked_out",
    "otterworks_db_pool_capacity",
    "otterworks_db_statement_timeouts_total",
)


def test_settings_read_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOC_SVC_FOLDER_DIGEST_ENABLED", "true")
    monkeypatch.setenv("DOC_SVC_FOLDER_DIGEST_INTERVAL_SECONDS", "5")
    monkeypatch.setenv("DOC_SVC_FOLDER_DIGEST_CONCURRENCY", "8")
    monkeypatch.setenv("DOC_SVC_DB_STATEMENT_TIMEOUT_MS", "3000")
    monkeypatch.setenv("DOC_SVC_DB_POOL_SIZE", "5")
    monkeypatch.setenv("DOC_SVC_DB_MAX_OVERFLOW", "0")
    s = Settings(_env_file=None)
    assert s.folder_digest_enabled is True
    assert s.folder_digest_interval_seconds == 5
    assert s.folder_digest_concurrency == 8
    assert s.db_statement_timeout_ms == 3000
    assert (s.db_pool_size, s.db_max_overflow) == (5, 0)


def test_statement_timeout_only_set_when_positive() -> None:
    assert engine_connect_args(0) == {}
    assert engine_connect_args(3000) == {"server_settings": {"statement_timeout": "3000"}}


def test_statement_timeout_detection() -> None:
    cancelled = QueryCanceledError("canceling statement due to statement timeout")
    wrapped = RuntimeError("adapter")
    wrapped.__cause__ = cancelled
    assert telemetry.is_statement_timeout(cancelled)
    assert telemetry.is_statement_timeout(DBAPIError("SELECT 1", {}, wrapped))
    assert not telemetry.is_statement_timeout(DBAPIError("SELECT 1", {}, RuntimeError("x")))
    assert not telemetry.is_statement_timeout(None)


def test_timeouts_are_counted_by_source(capsys: pytest.CaptureFixture[str]) -> None:
    def count(source: str) -> float:
        return (
            REGISTRY.get_sample_value("otterworks_db_statement_timeouts_total", {"source": source})
            or 0.0
        )

    api, worker = count("api"), count("worker")
    telemetry.record_statement_timeout("SELECT " + "x" * 500)
    token = telemetry.db_source.set("worker")
    try:
        telemetry.record_statement_timeout("SELECT count(*) FROM documents")
    finally:
        telemetry.db_source.reset(token)
    assert (count("api"), count("worker")) == (api + 1, worker + 1)
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    timeouts = [e for e in events if e["event"] == "db_statement_timeout"]
    assert [e["source"] for e in timeouts] == ["api", "worker"]
    assert len(timeouts[0]["statement"]) == telemetry.STATEMENT_PREFIX_CHARS


def test_pool_capacity_is_size_plus_overflow() -> None:
    eng = create_async_engine(
        "postgresql+asyncpg://u:p@localhost:1/db", pool_size=5, max_overflow=0
    )
    telemetry.instrument_pool(eng, 5, 0)
    assert REGISTRY.get_sample_value("otterworks_db_pool_capacity") == 5
    assert REGISTRY.get_sample_value("otterworks_db_pool_checked_out") == 0


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_new_series(client: AsyncClient) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    for name in NEW_METRICS:
        assert f"# TYPE {name} " in resp.text, name
