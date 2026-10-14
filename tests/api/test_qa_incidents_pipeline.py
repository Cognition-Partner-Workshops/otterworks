"""Black-box QA for the incident-responder observability pipeline.

Runs against the local incident stack (``make incident-up UI=1``): the API
gateway, document-service telemetry headers, Prometheus, Alertmanager, the
local alert sink and Jaeger.  Observability endpoints are overridable with
OTTERWORKS_PROMETHEUS_URL / OTTERWORKS_ALERTMANAGER_URL /
OTTERWORKS_ALERT_SINK_URL / OTTERWORKS_JAEGER_URL.
"""

import os
from typing import Any

import httpx
import pytest
from conftest import ApiClient

pytestmark = pytest.mark.api_flow

PROMETHEUS_URL = os.getenv("OTTERWORKS_PROMETHEUS_URL", "http://localhost:9090")
ALERTMANAGER_URL = os.getenv("OTTERWORKS_ALERTMANAGER_URL", "http://localhost:9093")
SINK_URL = os.getenv("OTTERWORKS_ALERT_SINK_URL", "http://localhost:9095")
JAEGER_URL = os.getenv("OTTERWORKS_JAEGER_URL", "http://localhost:16686")

INCIDENT_ALERTS = {
    "DocumentListLatencyHigh",
    "DocumentListQueryFanout",
    "RequestLogVolumeNearFull",
    "DocumentServiceErrorRateHigh",
    "DocumentServiceMemoryHigh",
    "DocumentStatsRollupDuplicated",
}
LIST_HANDLER = "/api/v1/documents/"


def _get(url: str, **params: Any) -> httpx.Response:
    try:
        return httpx.get(url, params=params or None, timeout=10)
    except httpx.HTTPError as exc:
        pytest.skip(f"incident observability stack not reachable at {url}: {exc}")


def _prom_query(expr: str) -> list[dict[str, Any]]:
    response = _get(f"{PROMETHEUS_URL}/api/v1/query", query=expr)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success", body
    return body["data"]["result"]


def _list_documents(api_client: ApiClient, headers: dict[str, str]) -> httpx.Response:
    response = api_client.client.get("/api/v1/documents/", headers=headers)
    assert response.status_code == 200, response.text
    return response


def test_document_list_through_gateway_carries_telemetry_headers(api_client: ApiClient):
    user = api_client.register_user("qa-incidents-headers")
    api_client.create_document(user, "QA incidents header probe", "body")

    response = _list_documents(api_client, user.auth_headers)

    assert int(response.headers["X-DB-Queries"]) >= 1
    assert float(response.headers["X-Request-Duration-Ms"]) >= 0
    assert response.headers.get("X-Request-ID")
    assert any(item["title"] == "QA incidents header probe" for item in response.json()["items"])


def test_document_list_query_count_grows_with_page_size_n_plus_one(api_client: ApiClient):
    """Characterises the planted n-plus-one flaw: one version query per row."""
    user = api_client.register_user("qa-incidents-fanout")
    api_client.create_document(user, "QA fanout 0", "body")
    small = int(_list_documents(api_client, user.auth_headers).headers["X-DB-Queries"])

    for i in range(1, 11):
        api_client.create_document(user, f"QA fanout {i}", "body")
    large = int(_list_documents(api_client, user.auth_headers).headers["X-DB-Queries"])

    assert large >= small + 10, (small, large)


@pytest.mark.xfail(strict=True, reason="planted n-plus-one bug on main (DocumentListQueryFanout)")
def test_document_list_query_count_is_constant_after_fix(api_client: ApiClient):
    user = api_client.register_user("qa-incidents-fixed")
    api_client.create_document(user, "QA fixed 0", "body")
    small = int(_list_documents(api_client, user.auth_headers).headers["X-DB-Queries"])
    for i in range(1, 11):
        api_client.create_document(user, f"QA fixed {i}", "body")
    large = int(_list_documents(api_client, user.auth_headers).headers["X-DB-Queries"])

    assert large == small


def test_prometheus_scrapes_a_healthy_document_service_target():
    response = _get(f"{PROMETHEUS_URL}/api/v1/targets", state="active")
    assert response.status_code == 200, response.text
    targets = [
        t for t in response.json()["data"]["activeTargets"]
        if t["labels"].get("job") == "document-service"
    ]
    assert targets, "no document-service scrape job"
    assert any(t["health"] == "up" for t in targets), targets


def test_prometheus_loads_every_incident_alert_rule_with_paging_labels():
    response = _get(f"{PROMETHEUS_URL}/api/v1/rules", type="alert")
    assert response.status_code == 200, response.text
    rules = {
        rule["name"]: rule
        for group in response.json()["data"]["groups"]
        for rule in group["rules"]
    }
    assert INCIDENT_ALERTS <= rules.keys(), INCIDENT_ALERTS - rules.keys()
    paged = {name for name in INCIDENT_ALERTS if rules[name]["labels"].get("page") == "devin"}
    assert paged == INCIDENT_ALERTS - {"DocumentListQueryFanout"}, paged
    for name in INCIDENT_ALERTS:
        labels = rules[name]["labels"]
        assert labels.get("service") == "document-service", (name, labels)
    for name in paged:
        assert rules[name]["annotations"].get("runbook_url"), name


def test_document_list_requests_are_recorded_under_the_alerted_handler(api_client: ApiClient):
    user = api_client.register_user("qa-incidents-metrics")
    _list_documents(api_client, user.auth_headers)

    api_client.poll_until(
        lambda: _prom_query(
            f'http_requests_total{{job="document-service",handler="{LIST_HANDLER}",method="GET"}}'
        ),
        description="document list counter in Prometheus",
        timeout_seconds=45,
        interval_seconds=3,
    )
    fanout = _prom_query(
        f'otterworks_db_queries_per_request_count{{handler="{LIST_HANDLER}"}}'
    )
    assert fanout, "SQL fan-out histogram missing for the list handler"


@pytest.mark.parametrize(
    "metric",
    [
        "otterworks_request_log_bytes",
        "otterworks_request_log_capacity_bytes",
        "otterworks_process_resident_memory_bytes",
    ],
)
def test_incident_gauges_are_scraped(metric: str):
    assert _prom_query(f'{metric}{{job="document-service"}}'), metric


def test_alertmanager_is_ready_and_routes_devin_pages():
    ready = _get(f"{ALERTMANAGER_URL}/-/ready")
    assert ready.status_code == 200, ready.text
    status = _get(f"{ALERTMANAGER_URL}/api/v2/status")
    assert status.status_code == 200, status.text
    config = status.json()["config"]["original"]
    assert "devin-oncall" in config
    assert "slack-oncall" in config
    assert "page" in config and "devin" in config


def test_alertmanager_receivers_include_responder_routes():
    response = _get(f"{ALERTMANAGER_URL}/api/v2/receivers")
    assert response.status_code == 200, response.text
    names = {r["name"] for r in response.json()}
    assert {"devin-oncall", "slack-oncall", "sink"} <= names, names


def test_alert_sink_health_and_receivers():
    assert _get(f"{SINK_URL}/health").json() == {"status": "ok"}
    for receiver in ("devin", "slack", "sink"):
        response = _get(f"{SINK_URL}/{receiver}")
        assert response.status_code == 200, response.text
        assert isinstance(response.json(), list)
    assert _get(f"{SINK_URL}/not-a-receiver").status_code == 404


def test_jaeger_receives_document_service_traces(api_client: ApiClient):
    user = api_client.register_user("qa-incidents-trace")
    _list_documents(api_client, user.auth_headers)

    services = api_client.poll_until(
        lambda: _get(f"{JAEGER_URL}/api/services").json()["data"] or [],
        predicate=lambda data: "document-service" in data,
        description="document-service in Jaeger",
        timeout_seconds=30,
        interval_seconds=2,
    )
    assert "document-service" in services
    def _list_traces() -> list[dict[str, Any]]:
        data = _get(
            f"{JAEGER_URL}/api/traces",
            service="document-service",
            operation=f"GET {LIST_HANDLER}",
            limit="20",
            lookback="1h",
        ).json()["data"]
        return [t for t in data if len(t["spans"]) > 1]

    # BatchSpanProcessor flushes every few seconds, so allow for export lag.
    traces = api_client.poll_until(
        _list_traces,
        description="multi-span document list trace in Jaeger",
        timeout_seconds=45,
        interval_seconds=3,
    )
    operations = {s["operationName"] for s in traces[0]["spans"]}
    assert any(op.startswith("SELECT") for op in operations), operations
