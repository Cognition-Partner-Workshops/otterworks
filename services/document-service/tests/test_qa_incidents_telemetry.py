"""QA (incidents): the telemetry every incident alert is keyed on is exported correctly.

These pin the metric names, labels and response headers that
observability/prometheus/incident_alerts.yml and incident/incident.py read.
"""

import uuid

import pytest
from httpx import AsyncClient

from app import telemetry
from app.chaos import FLAG_RENDER_CACHE, FLAG_REQUEST_LOG
from app.services.render_cache import RenderCache

INCIDENT_METRICS = (
    "otterworks_db_queries_per_request",
    "otterworks_db_query_duration_seconds",
    "otterworks_db_queries_total",
    "otterworks_process_resident_memory_bytes",
    "otterworks_process_memory_limit_bytes",
    "otterworks_render_cache_entries",
    "otterworks_request_log_bytes",
    "otterworks_request_log_capacity_bytes",
    "otterworks_rollup_runs_total",
    "otterworks_rollup_duplicate_windows",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("metric", INCIDENT_METRICS)
async def test_metrics_endpoint_exposes_incident_metric(client: AsyncClient, metric: str) -> None:
    # Touch every collector so labelled series are materialised.
    await client.get("/api/v1/documents/", params={"owner_id": str(uuid.uuid4())})
    telemetry.RENDER_CACHE_ENTRIES.labels(telemetry.SERVICE).set(0)
    telemetry.REQUEST_LOG_BYTES.labels(telemetry.SERVICE).set(0)
    telemetry.REQUEST_LOG_CAPACITY_BYTES.labels(telemetry.SERVICE).set(1)
    telemetry.ROLLUP_RUNS_TOTAL.labels(telemetry.SERVICE, "success").inc(0)
    telemetry.ROLLUP_DUPLICATE_WINDOWS.labels(telemetry.SERVICE).set(0)
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert metric in resp.text


@pytest.mark.asyncio
async def test_list_response_carries_query_and_duration_headers(
    client: AsyncClient, owner_id: uuid.UUID
) -> None:
    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    assert resp.status_code == 200
    assert int(resp.headers["X-DB-Queries"]) >= 1
    assert float(resp.headers["X-Request-Duration-Ms"]) >= 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health", "/metrics"])
async def test_probe_paths_do_not_carry_query_headers(client: AsyncClient, path: str) -> None:
    resp = await client.get(path)
    assert resp.status_code == 200
    assert "X-DB-Queries" not in resp.headers


@pytest.mark.asyncio
async def test_list_histogram_uses_the_handler_label_the_alert_matches(
    client: AsyncClient, owner_id: uuid.UUID
) -> None:
    await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    text = (await client.get("/metrics")).text
    assert 'otterworks_db_queries_per_request_count{handler="/api/v1/documents/"' in text
    assert 'http_request_duration_seconds_bucket{handler="/api/v1/documents/"' in text


@pytest.mark.asyncio
async def test_detail_route_is_labelled_by_template_not_raw_path(
    client: AsyncClient, owner_id: uuid.UUID
) -> None:
    doc_id = uuid.uuid4()
    await client.get(f"/api/v1/documents/{doc_id}")
    text = (await client.get("/metrics")).text
    assert str(doc_id) not in text
    assert 'handler="/api/v1/documents/{document_id}"' in text


def test_latency_buckets_straddle_the_one_second_page_threshold() -> None:
    assert 1.0 in telemetry.LATENCY_BUCKETS
    assert min(telemetry.LATENCY_BUCKETS) < 0.1
    assert max(telemetry.LATENCY_BUCKETS) >= 5.0
    assert list(telemetry.LATENCY_BUCKETS) == sorted(telemetry.LATENCY_BUCKETS)


def test_query_buckets_straddle_the_fanout_threshold() -> None:
    buckets = telemetry.DB_QUERIES_PER_REQUEST._upper_bounds
    assert any(b <= 5 for b in buckets)
    assert any(20 < b < 50 for b in buckets)
    assert any(b >= 104 for b in buckets)


def test_rss_reader_returns_positive_bytes_on_linux() -> None:
    assert telemetry._read_rss_bytes() > 0


def test_rss_reader_survives_missing_proc(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise OSError("no /proc")

    monkeypatch.setattr("builtins.open", boom)
    assert telemetry._read_rss_bytes() == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("268435456\n", 268435456), ("max\n", 0), ("9223372036854771712", 0)],
)
def test_memory_limit_reader_parses_cgroup_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path, raw: str, expected: int
) -> None:
    limit = tmp_path / "memory.max"
    limit.write_text(raw)
    real_open = open

    def fake_open(path, *a, **k):
        if path == "/sys/fs/cgroup/memory.max":
            return real_open(limit, *a, **k)
        raise OSError(path)

    monkeypatch.setattr("builtins.open", fake_open)
    assert telemetry._read_memory_limit_bytes() == expected


def test_memory_limit_reader_returns_zero_without_cgroup(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise OSError("absent")

    monkeypatch.setattr("builtins.open", boom)
    assert telemetry._read_memory_limit_bytes() == 0


def test_chaos_flag_keys_match_the_scenario_catalog() -> None:
    assert FLAG_REQUEST_LOG == "chaos:document-service:request_log"
    assert FLAG_RENDER_CACHE == "chaos:document-service:render_cache"


class _Doc:
    def __init__(self, version: int = 1) -> None:
        self.id = uuid.uuid4()
        self.version = version
        self.title = "t"
        self.content = "c"


def _gauge() -> float:
    return telemetry.RENDER_CACHE_ENTRIES.labels(telemetry.SERVICE)._value.get()


def test_render_cache_put_get_and_gauge() -> None:
    cache = RenderCache()
    doc = _Doc()
    assert cache.get(doc, "html") is None
    cache.put(doc, "html", "<p>c</p>", "text/html")
    assert cache.get(doc, "html") == ("<p>c</p>", "text/html")
    assert len(cache) == 1
    assert _gauge() == 1


def test_render_cache_keys_by_version_and_format() -> None:
    cache = RenderCache()
    doc = _Doc()
    cache.put(doc, "html", "a", "text/html")
    cache.put(doc, "markdown", "b", "text/markdown")
    doc.version = 2
    assert cache.get(doc, "html") is None
    cache.put(doc, "html", "c", "text/html")
    assert len(cache) == 3


def test_render_cache_clear_resets_gauge() -> None:
    cache = RenderCache()
    cache.put(_Doc(), "html", "a", "text/html")
    cache.clear()
    assert len(cache) == 0
    assert _gauge() == 0
