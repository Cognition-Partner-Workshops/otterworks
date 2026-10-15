"""Incident-responder harness: black-box checks of the alerting/observability path.

Runs against the local Compose stack with the incident overlay (`make incident-up`):
document-service metrics, Prometheus rules/targets, Alertmanager routing, the local
alert sink, Grafana's provisioned incident dashboard, and the Redis chaos flags that
arm the `log-flood` and `cache-leak` scenarios. Every probe skips cleanly when its
backend is not reachable, so `pytest tests/api --collect-only` stays green in CI.

Do not run the chaos-flag tests while `incident.py arm` is driving a scenario: they
toggle the same Redis keys the harness uses.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator

import httpx
import pytest


pytestmark = [pytest.mark.api_flow, pytest.mark.incident]

DOC_SERVICE_URL = os.getenv("INCIDENT_BASE_URL", "http://localhost:8083").rstrip("/")
PROM_URL = os.getenv("INCIDENT_PROM_URL", "http://localhost:9090").rstrip("/")
ALERTMANAGER_URL = os.getenv("INCIDENT_ALERTMANAGER_URL", "http://localhost:9093").rstrip("/")
SINK_URL = os.getenv("INCIDENT_SINK_URL", "http://localhost:9095").rstrip("/")
GRAFANA_URL = os.getenv("INCIDENT_GRAFANA_URL", "http://localhost:3001").rstrip("/")
GRAFANA_USER = os.getenv("GRAFANA_ADMIN_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "otterworks")
REDIS_URL = os.getenv("INCIDENT_REDIS_URL", "redis://localhost:6379/0")

FLAG_REQUEST_LOG = "chaos:document-service:request_log"
FLAG_RENDER_CACHE = "chaos:document-service:render_cache"
FLAG_CACHE_SECONDS = 2.0

INCIDENT_ALERTS = {
    "DocumentListLatencyHigh": "n-plus-one",
    "DocumentListQueryFanout": "n-plus-one",
    "RequestLogVolumeNearFull": "log-flood",
    "DocumentServiceErrorRateHigh": "log-flood",
    "DocumentServiceMemoryHigh": "cache-leak",
    "DocumentStatsRollupDuplicated": "double-run",
}
DASHBOARD_UID = "otterworks-incident-responder"
LIST_HANDLER = "/api/v1/documents/"
METRIC_LINE = re.compile(r"^(?P<name>[a-z_]+)(?:\{(?P<labels>[^}]*)\})? (?P<value>\S+)$")


def _get(url: str, **kwargs) -> httpx.Response:
    try:
        return httpx.get(url, timeout=10.0, **kwargs)
    except httpx.HTTPError as exc:
        pytest.skip(f"{url} is not reachable: {exc}")


def _metrics() -> dict[tuple[str, str], float]:
    response = _get(f"{DOC_SERVICE_URL}/metrics")
    assert response.status_code == 200
    samples: dict[tuple[str, str], float] = {}
    for line in response.text.splitlines():
        match = METRIC_LINE.match(line)
        if match:
            samples[(match["name"], match["labels"] or "")] = float(match["value"])
    return samples


def _sample(samples: dict[tuple[str, str], float], name: str, **labels: str) -> float | None:
    for (sample_name, sample_labels), value in samples.items():
        if sample_name == name and all(f'{k}="{v}"' in sample_labels for k, v in labels.items()):
            return value
    return None


def _prom(path: str, **params: str) -> dict:
    response = _get(f"{PROM_URL}{path}", params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success", body
    return body["data"]


@pytest.fixture
def redis_client() -> Iterator[object]:
    redis = pytest.importorskip("redis")
    client = redis.Redis.from_url(REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
    try:
        client.ping()
    except redis.RedisError as exc:
        pytest.skip(f"Redis is not reachable at {REDIS_URL}: {exc}")
    yield client
    client.delete(FLAG_REQUEST_LOG, FLAG_RENDER_CACHE)


@pytest.fixture
def grafana() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=GRAFANA_URL, timeout=10.0) as client:
        try:
            response = client.post(
                "/login", json={"user": GRAFANA_USER, "password": GRAFANA_PASSWORD}
            )
        except httpx.HTTPError as exc:
            pytest.skip(f"Grafana is not reachable at {GRAFANA_URL}: {exc}")
        assert response.status_code == 200, response.text
        assert "grafana_session" in client.cookies
        yield client


# --- document-service telemetry ------------------------------------------------


def test_document_service_exports_incident_metrics(api_client):
    user = api_client.register_user("incident-metrics")
    # Disarm restarts document-service and empties the histograms: drive a request first.
    response = api_client.client.get(
        "/api/v1/documents/", headers=user.auth_headers, params={"owner_id": user.id}
    )
    assert response.status_code == 200, response.text
    samples = _metrics()
    for name in (
        "otterworks_db_queries_per_request_count",
        "otterworks_process_resident_memory_bytes",
        "otterworks_process_memory_limit_bytes",
        "otterworks_request_log_bytes",
        "otterworks_request_log_capacity_bytes",
        "otterworks_rollup_duplicate_windows",
    ):
        assert _sample(samples, name) is not None, f"{name} missing from /metrics"
    assert _sample(samples, "otterworks_db_queries_per_request_count", handler=LIST_HANDLER)
    assert _sample(samples, "otterworks_process_resident_memory_bytes") > 0


@pytest.mark.xfail(
    strict=True,
    reason="[PLANTED] incident/scenarios.yaml n-plus-one: DocumentService.list_documents runs "
    "one versions query per document, so SQL statements per list request scale with page size",
)
def test_document_list_query_fanout_is_constant(api_client):
    user = api_client.register_user("incident-fanout")
    for i in range(8):
        api_client.create_document(user, f"Fanout {i} {api_client.run_id}", "body")
    before = _metrics()
    response = api_client.client.get(
        "/api/v1/documents/", headers=user.auth_headers, params={"owner_id": user.id}
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 8
    after = _metrics()
    name_sum, name_count = (
        "otterworks_db_queries_per_request_sum",
        "otterworks_db_queries_per_request_count",
    )
    statements = (_sample(after, name_sum, handler=LIST_HANDLER) or 0) - (
        _sample(before, name_sum, handler=LIST_HANDLER) or 0
    )
    requests = (_sample(after, name_count, handler=LIST_HANDLER) or 0) - (
        _sample(before, name_count, handler=LIST_HANDLER) or 0
    )
    assert requests >= 1
    assert statements / requests <= 5


# --- Prometheus ------------------------------------------------------------------


def test_prometheus_loads_every_incident_rule():
    groups = _prom("/api/v1/rules", type="alert")["groups"]
    rules = {r["name"]: r for g in groups for r in g["rules"]}
    for alert, scenario in INCIDENT_ALERTS.items():
        assert alert in rules, f"{alert} not loaded by Prometheus"
        labels = rules[alert]["labels"]
        assert labels["scenario"] == scenario
        assert labels["service"] == "document-service"
        assert rules[alert]["health"] == "ok", rules[alert].get("lastError")
        assert "runbook_url" in rules[alert]["annotations"]
    assert "page" not in rules["DocumentListQueryFanout"]["labels"]
    paging = [a for a in INCIDENT_ALERTS if rules[a]["labels"].get("page") == "devin"]
    assert len(paging) == 5


def test_prometheus_scrapes_document_service():
    targets = _prom("/api/v1/targets", state="active")["activeTargets"]
    doc_targets = [t for t in targets if t["labels"].get("job") == "document-service"]
    assert doc_targets, "document-service is not a Prometheus scrape target"
    assert any(t["health"] == "up" for t in doc_targets), doc_targets


def test_prometheus_has_document_service_series():
    result = _prom(
        "/api/v1/query", query='otterworks_process_resident_memory_bytes{job="document-service"}'
    )["result"]
    assert result and float(result[0]["value"][1]) > 0


# --- Alertmanager + local alert sink ----------------------------------------------


def test_alertmanager_routes_pages_to_devin_and_slack_receivers():
    response = _get(f"{ALERTMANAGER_URL}/api/v2/status")
    assert response.status_code == 200
    body = response.json()
    assert body["cluster"]["status"] == "ready"
    config = body["config"]["original"]
    assert "devin-oncall" in config and "slack-oncall" in config
    assert "page = devin" in config or 'page="devin"' in config
    assert "http://alert-sink:9095/devin" in config


def test_alertmanager_receivers_are_registered():
    response = _get(f"{ALERTMANAGER_URL}/api/v2/receivers")
    assert response.status_code == 200
    names = {r["name"] for r in response.json()}
    assert {"devin-oncall", "slack-oncall"} <= names


def test_alert_sink_exposes_receiver_logs():
    health = _get(f"{SINK_URL}/health")
    assert health.status_code == 200
    for receiver in ("devin", "slack"):
        response = _get(f"{SINK_URL}/{receiver}")
        assert response.status_code == 200
        deliveries = response.json()
        assert isinstance(deliveries, list)
        for delivery in deliveries:
            assert {"received_at", "payload"} <= set(delivery)
            for alert in delivery["payload"].get("alerts", []):
                assert alert["labels"]["alertname"] in INCIDENT_ALERTS
    assert _get(f"{SINK_URL}/pagerduty").status_code == 404


# --- Grafana -----------------------------------------------------------------------


def test_grafana_form_login_and_incident_dashboard(grafana: httpx.Client):
    response = grafana.get(f"/api/dashboards/uid/{DASHBOARD_UID}")
    assert response.status_code == 200, response.text
    dashboard = response.json()["dashboard"]
    titles = " ".join(p.get("title", "") for p in dashboard["panels"]).lower()
    for fragment in ("latency", "sql", "request log", "memory", "rollup"):
        assert fragment in titles, f"no panel about {fragment!r}: {titles}"


def test_grafana_prometheus_datasource_is_healthy(grafana: httpx.Client):
    datasources = grafana.get("/api/datasources").json()
    prom = next((d for d in datasources if d["type"] == "prometheus"), None)
    assert prom, datasources
    health = grafana.get(f"/api/datasources/uid/{prom['uid']}/health")
    assert health.status_code == 200, health.text
    assert health.json()["status"] == "OK"


def test_grafana_rejects_wrong_password():
    try:
        response = httpx.post(
            f"{GRAFANA_URL}/login",
            json={"user": GRAFANA_USER, "password": "not-the-password"},
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        pytest.skip(f"Grafana is not reachable: {exc}")
    assert response.status_code == 401


# --- chaos flags ---------------------------------------------------------------------


def _wait_for_flag_window() -> None:
    time.sleep(FLAG_CACHE_SECONDS + 0.5)


def test_request_log_chaos_flag_grows_request_log(api_client, redis_client):
    user = api_client.register_user("incident-request-log")
    document = api_client.create_document(user, f"Log flood {api_client.run_id}", "x" * 2000)
    baseline = _sample(_metrics(), "otterworks_request_log_bytes") or 0.0

    redis_client.set(FLAG_REQUEST_LOG, "1", ex=120)
    _wait_for_flag_window()
    for _ in range(5):
        response = api_client.client.get(
            f"/api/v1/documents/{document['id']}", headers=user.auth_headers
        )
        assert response.status_code == 200
    grown = api_client.poll_until(
        lambda: _sample(_metrics(), "otterworks_request_log_bytes") or 0.0,
        lambda value: value > baseline,
        timeout_seconds=15,
        description="request-log bytes to grow with the flag on",
    )
    assert grown > baseline

    redis_client.delete(FLAG_REQUEST_LOG)
    _wait_for_flag_window()
    api_client.client.get(f"/api/v1/documents/{document['id']}", headers=user.auth_headers)
    settled = _sample(_metrics(), "otterworks_request_log_bytes")
    api_client.client.get(f"/api/v1/documents/{document['id']}", headers=user.auth_headers)
    assert _sample(_metrics(), "otterworks_request_log_bytes") == settled


def test_render_cache_chaos_flag_populates_cache(api_client, redis_client):
    user = api_client.register_user("incident-render-cache")
    document = api_client.create_document(user, f"Cache leak {api_client.run_id}", "body")
    redis_client.set(FLAG_RENDER_CACHE, "1", ex=120)
    _wait_for_flag_window()

    before = _sample(_metrics(), "otterworks_render_cache_entries") or 0.0
    url = f"/api/v1/documents/{document['id']}/export"
    first = api_client.client.get(url, headers=user.auth_headers, params={"format": "html"})
    second = api_client.client.get(url, headers=user.auth_headers, params={"format": "html"})
    assert first.status_code == second.status_code == 200
    assert first.text == second.text
    after = _sample(_metrics(), "otterworks_render_cache_entries")
    assert after is not None and after >= before + 1


@pytest.mark.xfail(
    strict=True,
    reason="[PLANTED] incident/scenarios.yaml cache-leak: render_cache never evicts, so each "
    "edit+export adds an entry until DocumentServiceMemoryHigh pages",
)
def test_render_cache_does_not_grow_per_edit(api_client, redis_client):
    user = api_client.register_user("incident-render-leak")
    document = api_client.create_document(user, f"Leak {api_client.run_id}", "body")
    redis_client.set(FLAG_RENDER_CACHE, "1", ex=120)
    _wait_for_flag_window()
    url = f"/api/v1/documents/{document['id']}"
    api_client.client.get(f"{url}/export", headers=user.auth_headers, params={"format": "html"})
    before = _sample(_metrics(), "otterworks_render_cache_entries") or 0.0
    for i in range(5):
        edit = api_client.client.patch(url, headers=user.auth_headers, json={"content": f"v{i}"})
        assert edit.status_code == 200, edit.text
        api_client.client.get(
            f"{url}/export", headers=user.auth_headers, params={"format": "html"}
        )
    after = _sample(_metrics(), "otterworks_render_cache_entries") or 0.0
    assert after - before <= 1
