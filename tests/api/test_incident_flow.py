"""Incident-responder telemetry through the local stack (`make incident-up`).

The gateway half runs against OTTERWORKS_API_BASE_URL like every api_flow test.
The observability half talks to the incident overlay's Prometheus,
Alertmanager, alert sink, Grafana and Jaeger and skips when they are not up.
Flaws planted on main for the incident lab are marked xfail with [PLANTED].
"""

import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest


pytestmark = [pytest.mark.api_flow]

INCIDENT_ALERTS = {
    "DocumentListLatencyHigh": "n-plus-one",
    "DocumentListQueryFanout": "n-plus-one",
    "RequestLogVolumeNearFull": "log-flood",
    # Generic 5xx guard: fires under log-flood but carries no scenario label.
    "DocumentServiceErrorRateHigh": None,
    "DocumentServiceMemoryHigh": "cache-leak",
    "DocumentStatsRollupDuplicated": "double-run",
}
PAGING_ALERTS = {
    "DocumentListLatencyHigh",
    "DocumentServiceErrorRateHigh",
    "RequestLogVolumeNearFull",
    "DocumentServiceMemoryHigh",
    "DocumentStatsRollupDuplicated",
}


def _url(env: str, default: str) -> str:
    return os.getenv(env, default).rstrip("/")


PROM = _url("INCIDENT_PROM_URL", "http://localhost:9090")
ALERTMANAGER = _url("INCIDENT_ALERTMANAGER_URL", "http://localhost:9093")
SINK = _url("INCIDENT_SINK_URL", "http://localhost:9095")
GRAFANA = _url("INCIDENT_GRAFANA_URL", "http://localhost:3001")
JAEGER = _url("INCIDENT_JAEGER_URL", "http://localhost:16686")
GRAFANA_AUTH = (
    os.getenv("INCIDENT_GRAFANA_USER", "admin"),
    os.getenv("INCIDENT_GRAFANA_PASSWORD", "otterworks"),
)
DASHBOARD_UID = "otterworks-incident-responder"


def _reachable(url: str) -> bool:
    try:
        return httpx.get(url, timeout=3).status_code < 500
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="module")
def obs() -> httpx.Client:
    if not _reachable(f"{PROM}/-/ready") or not _reachable(f"{ALERTMANAGER}/-/healthy"):
        pytest.skip("incident stack not running; start it with `make incident-up`")
    with httpx.Client(timeout=10) as client:
        yield client


def _prom(obs: httpx.Client, expr: str) -> list[dict]:
    response = obs.get(f"{PROM}/api/v1/query", params={"query": expr})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success", body
    return body["data"]["result"]


def _list(api_client, user, size: int) -> httpx.Response:
    response = api_client.client.get(
        "/api/v1/documents/", headers=user.auth_headers, params={"size": size}
    )
    assert response.status_code == 200, response.text
    return response


# ---------------------------------------------------------------------------
# gateway: the per-request telemetry the n-plus-one alert is built on
# ---------------------------------------------------------------------------


def test_document_list_exposes_query_count_and_duration_through_gateway(api_client):
    user = api_client.register_user("incident-headers")
    response = _list(api_client, user, 20)

    assert int(response.headers["X-DB-Queries"]) >= 1
    assert float(response.headers["X-Request-Duration-Ms"]) >= 0
    assert response.headers.get("X-Request-Id")


def test_document_list_query_count_reflects_page_contents(api_client):
    user = api_client.register_user("incident-fanout")
    empty = int(_list(api_client, user, 20).headers["X-DB-Queries"])
    for i in range(3):
        api_client.create_document(user, f"Incident fan-out {i} {api_client.run_id}", "body")
    body = _list(api_client, user, 20)
    assert body.json()["total"] == 3
    assert int(body.headers["X-DB-Queries"]) >= empty


@pytest.mark.xfail(
    reason="[PLANTED] incident scenario n-plus-one: DocumentService.list_documents "
    "issues one versions SELECT per document, so statements grow with page size",
    strict=False,
)
def test_document_list_statement_count_is_constant_in_page_size(api_client):
    user = api_client.register_user("incident-n-plus-one")
    for i in range(6):
        api_client.create_document(user, f"Incident n+1 {i} {api_client.run_id}", "body")
    small = int(_list(api_client, user, 1).headers["X-DB-Queries"])
    large = int(_list(api_client, user, 6).headers["X-DB-Queries"])
    assert large == small


# ---------------------------------------------------------------------------
# observability: rules, scrape, routing, dashboard, traces
# ---------------------------------------------------------------------------


def test_prometheus_loads_every_incident_alert_rule(obs):
    response = obs.get(f"{PROM}/api/v1/rules", params={"type": "alert"})
    assert response.status_code == 200
    rules = {
        rule["name"]: rule
        for group in response.json()["data"]["groups"]
        for rule in group["rules"]
    }
    for name, scenario in INCIDENT_ALERTS.items():
        assert name in rules, f"{name} missing from Prometheus"
        labels = rules[name]["labels"]
        assert labels["service"] == "document-service"
        assert labels.get("scenario") == scenario
        assert (labels.get("page") == "devin") == (name in PAGING_ALERTS), name
        assert rules[name]["health"] == "ok", rules[name]


def test_prometheus_scrapes_document_service(obs):
    result = _prom(obs, 'up{job="document-service"}')
    assert result, "document-service is not a Prometheus scrape target"
    assert any(sample["value"][1] == "1" for sample in result)


def test_incident_metrics_are_exported(obs, api_client):
    # The query histogram only has series once a request was observed, and a
    # disarm restarts document-service, so drive one list call first.
    user = api_client.register_user("incident-metrics")
    _list(api_client, user, 5)
    for metric in (
        "otterworks_db_queries_per_request_count",
        "otterworks_request_log_capacity_bytes",
        # otterworks_render_cache_entries is only set after a render/export;
        # the unit layer covers it.
        "otterworks_process_resident_memory_bytes",
        "otterworks_rollup_duplicate_windows",
    ):
        api_client.poll_until(
            lambda metric=metric: _prom(obs, metric),
            bool,
            timeout_seconds=45,
            interval_seconds=3,
            description=f"{metric} to have a series in Prometheus",
        )


def test_gateway_list_request_is_counted_by_prometheus(obs, api_client):
    user = api_client.register_user("incident-scrape")
    expr = (
        'sum(otterworks_db_queries_per_request_count{handler="/api/v1/documents/"})'
    )
    before = float((_prom(obs, expr) or [{"value": [0, "0"]}])[0]["value"][1])
    _list(api_client, user, 5)
    api_client.poll_until(
        lambda: float((_prom(obs, expr) or [{"value": [0, "0"]}])[0]["value"][1]),
        lambda value: value > before,
        timeout_seconds=45,
        interval_seconds=3,
        description="the list request to show up in the scraped query histogram",
    )


def test_alertmanager_routes_devin_pages_and_silences_nothing(obs):
    status = obs.get(f"{ALERTMANAGER}/api/v2/status")
    assert status.status_code == 200
    config = status.json()["config"]["original"]
    for receiver in ("name: sink", "name: devin-oncall", "name: slack-oncall"):
        assert receiver in config, f"{receiver} missing from Alertmanager config"
    assert "page=\"devin\"" in config.replace(" ", "") or "page=devin" in config.replace(
        " ", ""
    ), "no route matches page=devin"
    silences = obs.get(f"{ALERTMANAGER}/api/v2/silences").json()
    assert not [s for s in silences if s["status"]["state"] == "active"]


def test_non_paging_alert_reaches_only_the_sink(obs):
    if not _reachable(f"{SINK}/"):
        pytest.skip("alert sink not reachable")
    name = f"QaIncidentPipelineProbe{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    probe = [
        {
            "labels": {"alertname": name, "service": "qa-probe", "severity": "info"},
            "annotations": {"summary": "QA probe of the alert pipeline"},
            "startsAt": now.isoformat(),
            "endsAt": (now + timedelta(minutes=2)).isoformat(),
        }
    ]
    assert obs.post(f"{ALERTMANAGER}/api/v2/alerts", json=probe).status_code == 200

    def captured(receiver: str) -> bool:
        records = obs.get(f"{SINK}/{receiver}").json() or []
        return any(
            a.get("labels", {}).get("alertname") == name
            for r in records
            for a in (r.get("payload") or {}).get("alerts", [])
        )

    deadline = time.monotonic() + 60
    while not captured("sink"):
        assert time.monotonic() < deadline, f"{name} never reached the alert sink"
        time.sleep(3)
    assert not captured("devin"), "a non-paging alert must not page Devin"


def test_grafana_incident_dashboard_is_provisioned(obs):
    response = obs.get(f"{GRAFANA}/api/dashboards/uid/{DASHBOARD_UID}", auth=GRAFANA_AUTH)
    if response.status_code == 401:
        pytest.skip("Grafana admin credentials differ from the local defaults")
    assert response.status_code == 200, response.text
    dashboard = response.json()["dashboard"]
    titles = " | ".join(p.get("title", "") for p in dashboard["panels"]).lower()
    for needle in ("latency", "sql statements", "request-log", "memory", "rollup", "trace"):
        assert needle in titles, f"dashboard has no {needle!r} panel: {titles}"


def test_grafana_datasources_are_healthy(obs):
    response = obs.get(f"{GRAFANA}/api/datasources", auth=GRAFANA_AUTH)
    if response.status_code == 401:
        pytest.skip("Grafana admin credentials differ from the local defaults")
    kinds = {ds["type"] for ds in response.json()}
    assert {"prometheus", "jaeger"} <= kinds, kinds


def test_jaeger_has_document_service_list_traces(obs, api_client):
    if not _reachable(f"{JAEGER}/"):
        pytest.skip("Jaeger not reachable")
    user = api_client.register_user("incident-trace")
    _list(api_client, user, 5)

    def traces() -> list:
        response = obs.get(
            f"{JAEGER}/api/traces",
            params={
                "service": "document-service",
                "operation": "GET /api/v1/documents/",
                "lookback": "1h",
                "limit": 5,
            },
        )
        return response.json().get("data") or []

    found = api_client.poll_until(
        traces, timeout_seconds=45, interval_seconds=3, description="document list traces"
    )
    spans = [s["operationName"] for s in found[0]["spans"]]
    assert any(op.startswith("SELECT") for op in spans), spans
