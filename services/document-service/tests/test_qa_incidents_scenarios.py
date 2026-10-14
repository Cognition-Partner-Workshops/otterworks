"""QA (incidents): the four planted document-service flaws are present and observable.

`main` ships these flaws on purpose (incident/README.md). The characterization
tests prove each scenario is armable -- the telemetry the alert reads moves the
way the runbook says. The `xfail(strict=True)` tests encode the runbook's
"correct fix" contract: they are expected to fail on `main` and will flip to
XPASS (failing the run) on a branch that fixes the flaw, which is the signal to
drop the marker there.
"""

import json
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import telemetry
from app.chaos import FLAG_REQUEST_LOG
from app.jobs import stats_rollup
from app.middleware import request_log as request_log_module
from app.middleware.request_log import RequestLog
from app.models.document import DocumentStatsRollup
from app.services.render_cache import RenderCache

PLANTED = "planted incident flaw on main (incident/README.md); do not fix on main"
WINDOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


async def _seed(client: AsyncClient, owner_id: uuid.UUID, n: int) -> None:
    for i in range(n):
        resp = await client.post(
            "/api/v1/documents/",
            json={"title": f"QA {i}", "content": "otter " * 10, "owner_id": str(owner_id)},
        )
        assert resp.status_code == 201, resp.text


async def _list_queries(client: AsyncClient, owner_id: uuid.UUID, size: int) -> int:
    resp = await client.get(
        "/api/v1/documents/", params={"owner_id": str(owner_id), "size": size}
    )
    assert resp.status_code == 200
    return int(resp.headers["X-DB-Queries"])


# ---- n-plus-one ----------------------------------------------------------


@pytest.mark.asyncio
async def test_n_plus_one_query_count_grows_with_page(
    client: AsyncClient, owner_id: uuid.UUID
) -> None:
    await _seed(client, owner_id, 12)
    small = await _list_queries(client, owner_id, 2)
    large = await _list_queries(client, owner_id, 12)
    assert large - small == 10, (small, large)


@pytest.mark.asyncio
async def test_n_plus_one_fanout_crosses_the_alert_threshold(
    client: AsyncClient, owner_id: uuid.UUID
) -> None:
    await _seed(client, owner_id, 25)
    assert await _list_queries(client, owner_id, 25) > 20


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, reason=PLANTED)
async def test_n_plus_one_fix_contract_constant_queries(
    client: AsyncClient, owner_id: uuid.UUID
) -> None:
    await _seed(client, owner_id, 12)
    assert await _list_queries(client, owner_id, 2) == await _list_queries(client, owner_id, 12)


# ---- log-flood -----------------------------------------------------------


@pytest.mark.asyncio
async def test_log_flood_flag_off_writes_nothing(
    client: AsyncClient, owner_id: uuid.UUID, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(request_log_module, "request_log", RequestLog(str(tmp_path)))
    await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_log_flood_armed_grows_the_bytes_gauge_per_request(
    client: AsyncClient, owner_id: uuid.UUID, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(request_log_module, "flag_active", lambda key: key == FLAG_REQUEST_LOG)
    log = RequestLog(str(tmp_path))
    monkeypatch.setattr(request_log_module, "request_log", log)
    gauge = telemetry.REQUEST_LOG_BYTES.labels(telemetry.SERVICE)
    sizes = []
    for _ in range(3):
        await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
        sizes.append(gauge._value.get())
    assert sizes[0] > 0 and sizes[0] < sizes[1] < sizes[2]
    assert telemetry.REQUEST_LOG_CAPACITY_BYTES.labels(telemetry.SERVICE)._value.get() > 0


@pytest.mark.asyncio
async def test_log_flood_skips_probe_paths(
    client: AsyncClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(request_log_module, "flag_active", lambda key: True)
    monkeypatch.setattr(request_log_module, "request_log", RequestLog(str(tmp_path)))
    for path in ("/health", "/metrics"):
        await client.get(path)
    assert list(tmp_path.iterdir()) == []


def test_log_flood_purge_empties_directory_and_gauge(tmp_path) -> None:
    log = RequestLog(str(tmp_path))
    for i in range(5):
        log.append({"i": i, "body": "x" * 100})
    assert log._bytes > 500
    log.purge()
    assert list(tmp_path.iterdir()) == []
    assert log._bytes == 0
    assert telemetry.REQUEST_LOG_BYTES.labels(telemetry.SERVICE)._value.get() == 0


def test_log_flood_rescan_counts_existing_bytes(tmp_path) -> None:
    (tmp_path / "old.jsonl").write_text(json.dumps({"a": 1}) + "\n")
    log = RequestLog(str(tmp_path))
    assert log._bytes == len(json.dumps({"a": 1})) + 1


@pytest.mark.xfail(strict=True, reason=PLANTED)
def test_log_flood_fix_contract_bounded_file_set(tmp_path) -> None:
    log = RequestLog(str(tmp_path))
    for i in range(2000):
        log.append({"i": i, "body": "x" * 4096})
    total = sum(p.stat().st_size for p in tmp_path.iterdir())
    assert total < 2 * 1024 * 1024


# ---- cache-leak ----------------------------------------------------------


class _Doc:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.version = 1
        self.title = "t"
        self.content = "c" * 64


def test_cache_leak_every_edit_adds_an_entry() -> None:
    cache = RenderCache()
    doc = _Doc()
    for v in range(1, 51):
        doc.version = v
        cache.put(doc, "html", "body", "text/html")
    assert len(cache) == 50
    assert telemetry.RENDER_CACHE_ENTRIES.labels(telemetry.SERVICE)._value.get() == 50


@pytest.mark.xfail(strict=True, reason=PLANTED)
def test_cache_leak_fix_contract_bounded_cache() -> None:
    cache = RenderCache()
    doc = _Doc()
    for v in range(1, 5001):
        doc.version = v
        cache.put(doc, "html", "body", "text/html")
    assert len(cache) <= 1000


# ---- double-run ----------------------------------------------------------


def test_double_run_window_is_aligned_to_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stats_rollup.settings, "rollup_interval_seconds", 60)
    w = stats_rollup.current_window(datetime(2026, 1, 1, 12, 0, 59, tzinfo=UTC))
    assert w == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    w2 = stats_rollup.current_window(datetime(2026, 1, 1, 12, 1, 0, tzinfo=UTC))
    assert (w2 - w).total_seconds() == 60


@pytest.mark.asyncio
async def test_double_run_two_hosts_produce_a_duplicate_window(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(stats_rollup.socket, "gethostname", lambda: "replica-a")
    await stats_rollup.compute_rollup(db_session, WINDOW)
    monkeypatch.setattr(stats_rollup.socket, "gethostname", lambda: "replica-b")
    await stats_rollup.compute_rollup(db_session, WINDOW)
    assert await stats_rollup.duplicate_windows(db_session, WINDOW) == 1


@pytest.mark.asyncio
async def test_double_run_distinct_windows_are_not_duplicates(db_session: AsyncSession) -> None:
    await stats_rollup.compute_rollup(db_session, WINDOW)
    await stats_rollup.compute_rollup(db_session, WINDOW.replace(minute=1))
    assert await stats_rollup.duplicate_windows(db_session, WINDOW) == 0


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, reason=PLANTED)
async def test_double_run_fix_contract_single_row_per_window(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    for host in ("replica-a", "replica-b"):
        monkeypatch.setattr(stats_rollup.socket, "gethostname", lambda h=host: h)
        await stats_rollup.compute_rollup(db_session, WINDOW)
    rows = (
        await db_session.execute(select(func.count()).select_from(DocumentStatsRollup))
    ).scalar_one()
    assert rows == 1
