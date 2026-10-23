"""Unit coverage for the four incident-responder scenarios (incident/scenarios.yaml).

Each scenario's flaw is PLANTED on main for the incident-responder lab, so the
"what the fix must guarantee" tests here are expected failures on main
(``xfail``, non-strict, so a fixed branch such as ``demo-incident`` reports them
as XPASS instead of breaking). The remaining tests pin the mechanics the
alerts and the verification gate depend on and pass on main.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from prometheus_client import REGISTRY
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chaos import FLAG_RENDER_CACHE, FLAG_REQUEST_LOG, FLAG_SLOW_QUERIES
from app.jobs import stats_rollup
from app.middleware import request_log as request_log_module
from app.middleware.request_log import RequestLog
from app.models.document import Document, DocumentStatsRollup, DocumentVersion
from app.services.render_cache import RenderCache
from app.telemetry import SERVICE

WINDOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _planted(scenario: str, why: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(reason=f"[PLANTED] incident scenario {scenario}: {why}", strict=False)


def _gauge(name: str) -> float | None:
    return REGISTRY.get_sample_value(name, {"service": SERVICE})


async def _seed(db: AsyncSession, owner_id: uuid.UUID, docs: int, versions: int = 2) -> None:
    for i in range(docs):
        doc = Document(title=f"Doc {i}", content="body", owner_id=owner_id, version=versions)
        db.add(doc)
        await db.flush()
        for v in range(1, versions + 1):
            db.add(
                DocumentVersion(
                    document_id=doc.id,
                    version_number=v,
                    title=doc.title,
                    content=f"v{v}",
                    created_by=owner_id,
                )
            )
    await db.commit()


async def _list_queries(client: AsyncClient, owner_id: uuid.UUID, size: int) -> int:
    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id), "size": size})
    assert resp.status_code == 200
    return int(resp.headers["X-DB-Queries"])


def _doc(title: str = "T", content: str = "C", version: int = 1) -> Document:
    return Document(id=uuid.uuid4(), title=title, content=content, version=version)


# ---------------------------------------------------------------------------
# chaos flags the scenarios arm
# ---------------------------------------------------------------------------


def test_chaos_flag_keys_match_the_scenario_catalog() -> None:
    assert FLAG_REQUEST_LOG == "chaos:document-service:request_log"
    assert FLAG_RENDER_CACHE == "chaos:document-service:render_cache"
    assert FLAG_SLOW_QUERIES == "chaos:document-service:slow_queries"


# ---------------------------------------------------------------------------
# n-plus-one: DocumentListLatencyHigh / DocumentListQueryFanout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_header_counts_statements_for_empty_page(
    client: AsyncClient, owner_id: uuid.UUID
) -> None:
    assert await _list_queries(client, owner_id, 20) >= 1


@pytest.mark.asyncio
async def test_list_still_returns_recent_documents(
    client: AsyncClient, db_session: AsyncSession, owner_id: uuid.UUID
) -> None:
    await _seed(db_session, owner_id, docs=3)
    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    body = resp.json()
    assert resp.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 3


@pytest.mark.asyncio
async def test_list_query_histogram_observes_list_handler(
    client: AsyncClient, owner_id: uuid.UUID
) -> None:
    labels = {"service": SERVICE, "handler": "/api/v1/documents/"}
    before = REGISTRY.get_sample_value("otterworks_db_queries_per_request_count", labels) or 0
    await _list_queries(client, owner_id, 5)
    after = REGISTRY.get_sample_value("otterworks_db_queries_per_request_count", labels)
    assert after == before + 1


@pytest.mark.asyncio
async def test_list_response_reports_duration_header(
    client: AsyncClient, owner_id: uuid.UUID
) -> None:
    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    assert float(resp.headers["X-Request-Duration-Ms"]) >= 0


@_planted("n-plus-one", "list_documents runs one versions SELECT per document on the page")
@pytest.mark.asyncio
async def test_list_statement_count_is_constant_in_page_size(
    client: AsyncClient, db_session: AsyncSession, owner_id: uuid.UUID
) -> None:
    await _seed(db_session, owner_id, docs=30)
    small = await _list_queries(client, owner_id, 2)
    large = await _list_queries(client, owner_id, 30)
    assert large == small


@_planted("n-plus-one", "a 100-row page issues ~104 statements instead of ~5")
@pytest.mark.asyncio
async def test_full_page_stays_under_query_fanout_alert_threshold(
    client: AsyncClient, db_session: AsyncSession, owner_id: uuid.UUID
) -> None:
    await _seed(db_session, owner_id, docs=40, versions=1)
    assert await _list_queries(client, owner_id, 40) <= 10


# ---------------------------------------------------------------------------
# log-flood: RequestLogVolumeNearFull / DocumentServiceErrorRateHigh
# ---------------------------------------------------------------------------


def test_request_log_append_publishes_bytes_gauge(tmp_path) -> None:
    log = RequestLog(str(tmp_path))
    log.append({"path": "/x", "status": 200})
    size = sum(p.stat().st_size for p in tmp_path.iterdir())
    assert _gauge("otterworks_request_log_bytes") == size
    assert (_gauge("otterworks_request_log_capacity_bytes") or 0) > 0


def test_request_log_purge_resets_gauge(tmp_path) -> None:
    log = RequestLog(str(tmp_path))
    log.append({"path": "/x"})
    log.purge()
    assert list(tmp_path.iterdir()) == []
    assert _gauge("otterworks_request_log_bytes") == 0


def test_request_log_rescans_existing_files(tmp_path) -> None:
    (tmp_path / "old.jsonl").write_text("x" * 123)
    RequestLog(str(tmp_path))
    assert _gauge("otterworks_request_log_bytes") == 123


def test_request_log_records_are_jsonl(tmp_path) -> None:
    log = RequestLog(str(tmp_path))
    for i in range(3):
        log.append({"i": i})
    (f,) = tmp_path.iterdir()
    assert [json.loads(line)["i"] for line in f.read_text().splitlines()] == [0, 1, 2]


@pytest.mark.asyncio
async def test_request_log_is_skipped_when_flag_off(
    client: AsyncClient, owner_id: uuid.UUID, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(request_log_module, "request_log", RequestLog(str(tmp_path)))
    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    assert resp.status_code == 200
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_request_log_skips_health_and_metrics(
    client: AsyncClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(request_log_module, "flag_active", lambda key: key == FLAG_REQUEST_LOG)
    monkeypatch.setattr(request_log_module, "request_log", RequestLog(str(tmp_path)))
    for path in ("/health", "/metrics"):
        assert (await client.get(path)).status_code == 200
    assert list(tmp_path.iterdir()) == []


@_planted("log-flood", "RequestLog.append grows one JSONL file forever (no rotation/cap)")
def test_request_log_stays_bounded_past_the_cap(tmp_path) -> None:
    log = RequestLog(str(tmp_path))
    record = {"response": "x" * 4096}
    for _ in range(2048):  # ~8 MiB
        log.append(record)
    total = sum(p.stat().st_size for p in tmp_path.iterdir())
    assert total <= 4 * 1024 * 1024


@_planted("log-flood", "a full request-log volume fails the request with a 500")
@pytest.mark.asyncio
async def test_request_log_write_failure_does_not_fail_the_request(
    client: AsyncClient, owner_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class FullDisk(RequestLog):
        def append(self, record: dict) -> None:
            raise OSError(28, "No space left on device")

    monkeypatch.setattr(request_log_module, "flag_active", lambda key: key == FLAG_REQUEST_LOG)
    monkeypatch.setattr(request_log_module, "request_log", FullDisk(str(tmp_path)))
    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# cache-leak: DocumentServiceMemoryHigh
# ---------------------------------------------------------------------------


def test_render_cache_miss_then_hit() -> None:
    cache, doc = RenderCache(), _doc()
    assert cache.get(doc, "html") is None
    cache.put(doc, "html", "<p>C</p>", "text/html")
    assert cache.get(doc, "html") == ("<p>C</p>", "text/html")


def test_render_cache_keys_on_version_and_format() -> None:
    cache, doc = RenderCache(), _doc()
    cache.put(doc, "html", "v1", "text/html")
    cache.put(doc, "markdown", "v1-md", "text/markdown")
    doc.version = 2
    assert cache.get(doc, "html") is None
    assert len(cache) == 2


def test_render_cache_publishes_entry_gauge_and_clear_resets_it() -> None:
    cache = RenderCache()
    for _ in range(3):
        cache.put(_doc(), "html", "b", "text/html")
    assert _gauge("otterworks_render_cache_entries") == 3
    cache.clear()
    assert len(cache) == 0
    assert _gauge("otterworks_render_cache_entries") == 0


@_planted("cache-leak", "RenderCache is an unbounded dict keyed per document version")
def test_render_cache_is_bounded() -> None:
    cache = RenderCache()
    for _ in range(5000):
        cache.put(_doc(), "html", "body", "text/html")
    assert len(cache) < 5000


@_planted("cache-leak", "every edit leaves the previous version's render (and source) cached")
def test_render_cache_drops_superseded_versions() -> None:
    cache, doc = RenderCache(), _doc()
    for v in range(1, 50):
        doc.version = v
        cache.put(doc, "html", "x" * 1024, "text/html")
    assert len(cache) <= 2


# ---------------------------------------------------------------------------
# double-run: DocumentStatsRollupDuplicated
# ---------------------------------------------------------------------------


async def _rollup_rows(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(DocumentStatsRollup))).scalar_one()


def test_current_window_truncates_to_the_window_start() -> None:
    now = datetime(2026, 1, 1, 12, 34, 56, tzinfo=UTC)
    window = stats_rollup.current_window(now)
    assert window <= now
    assert window.second == 0 and window.microsecond == 0


@pytest.mark.asyncio
async def test_rollup_counts_documents(db_session: AsyncSession, owner_id: uuid.UUID) -> None:
    await _seed(db_session, owner_id, docs=2, versions=3)
    row = await stats_rollup.compute_rollup(db_session, WINDOW)
    assert row.documents_total == 2
    assert row.versions_total == 6


@pytest.mark.asyncio
async def test_no_duplicate_windows_with_a_single_host(db_session: AsyncSession) -> None:
    await stats_rollup.compute_rollup(db_session, WINDOW)
    assert await stats_rollup.duplicate_windows(db_session, WINDOW) == 0


@_planted("double-run", "every replica computes and inserts the same rollup window")
@pytest.mark.asyncio
async def test_two_replicas_produce_one_row_per_window(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await stats_rollup.compute_rollup(db_session, WINDOW)
    monkeypatch.setattr(stats_rollup.socket, "gethostname", lambda: "replica-b")
    await stats_rollup.compute_rollup(db_session, WINDOW)
    assert await _rollup_rows(db_session) == 1
    assert await stats_rollup.duplicate_windows(db_session, WINDOW) == 0


@_planted("double-run", "no advisory lock / unique window_start guards concurrent rollups")
@pytest.mark.asyncio
async def test_concurrent_rollups_for_one_window_write_one_row(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    hosts = iter(["replica-a", "replica-b"])
    monkeypatch.setattr(stats_rollup.socket, "gethostname", lambda: next(hosts, "replica-c"))
    for _ in range(2):
        await asyncio.wait_for(stats_rollup.compute_rollup(db_session, WINDOW), timeout=5)
    assert await _rollup_rows(db_session) == 1
