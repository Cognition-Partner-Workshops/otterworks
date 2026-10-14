"""Live alert-lifecycle QA for the n-plus-one incident.

State-dependent, so opt-in via OTTERWORKS_INCIDENT_EXPECT:
  firing  - after `make incident-arm SCENARIO=n-plus-one` and the 1m `for:` window
  clear   - after `make incident-disarm`
"""

import os
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.api_flow

EXPECT = os.getenv("OTTERWORKS_INCIDENT_EXPECT", "")
PROMETHEUS_URL = os.getenv("OTTERWORKS_PROMETHEUS_URL", "http://localhost:9090")
ALERTMANAGER_URL = os.getenv("OTTERWORKS_ALERTMANAGER_URL", "http://localhost:9093")
SINK_URL = os.getenv("OTTERWORKS_ALERT_SINK_URL", "http://localhost:9095")
PAGED = "DocumentListLatencyHigh"
DIAGNOSTIC = "DocumentListQueryFanout"

requires_firing = pytest.mark.skipif(EXPECT != "firing", reason="set OTTERWORKS_INCIDENT_EXPECT=firing")
requires_clear = pytest.mark.skipif(EXPECT != "clear", reason="set OTTERWORKS_INCIDENT_EXPECT=clear")


def _json(url: str, **params: Any) -> Any:
    try:
        response = httpx.get(url, params=params or None, timeout=10)
    except httpx.HTTPError as exc:
        pytest.skip(f"incident stack not reachable at {url}: {exc}")
    assert response.status_code == 200, response.text
    return response.json()


def _prom_states() -> dict[str, str]:
    alerts = _json(f"{PROMETHEUS_URL}/api/v1/alerts")["data"]["alerts"]
    return {
        a["labels"]["alertname"]: a["state"]
        for a in alerts
        if a["labels"].get("service") == "document-service" and "scenario" in a["labels"]
    }


def _am_alerts() -> list[dict[str, Any]]:
    return _json(f"{ALERTMANAGER_URL}/api/v2/alerts", active="true")


def _prom_scalar(expr: str) -> float | None:
    result = _json(f"{PROMETHEUS_URL}/api/v1/query", query=expr)["data"]["result"]
    return float(result[0]["value"][1]) if result else None


def _devin_pages() -> list[dict[str, Any]]:
    return _json(f"{SINK_URL}/devin")


@requires_firing
def test_paged_alert_is_firing_in_prometheus():
    assert _prom_states().get(PAGED) == "firing", _prom_states()


@requires_firing
def test_diagnostic_fanout_alert_is_firing_but_not_paged():
    assert _prom_states().get(DIAGNOSTIC) == "firing", _prom_states()
    fanout = [a for a in _am_alerts() if a["labels"]["alertname"] == DIAGNOSTIC]
    assert all(a["labels"].get("page") != "devin" for a in fanout)


@requires_firing
def test_alertmanager_routes_the_page_to_devin_and_slack():
    paged = [a for a in _am_alerts() if a["labels"]["alertname"] == PAGED]
    assert paged, "page not delivered to Alertmanager"
    receivers = {r["name"] for a in paged for r in a["receivers"]}
    assert {"devin-oncall", "slack-oncall"} <= receivers, receivers
    assert paged[0]["annotations"].get("runbook_url")


@requires_firing
def test_sink_captured_a_firing_devin_page():
    firing = [
        r for r in _devin_pages()
        if r["payload"].get("status") == "firing"
        and any(a["labels"]["alertname"] == PAGED for a in r["payload"]["alerts"])
    ]
    assert firing, "Devin receiver never got the page"
    assert all(v == "<redacted>" for k, v in firing[-1]["headers"].items()
               if k.lower() in {"authorization", "x-webhook-secret"})


@requires_firing
def test_symptoms_cross_their_thresholds():
    p95 = _prom_scalar(
        "histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket"
        '{job="document-service",handler="/api/v1/documents/",method="GET"}[2m])))'
    )
    qpr = _prom_scalar(
        'sum(rate(otterworks_db_queries_per_request_sum{handler="/api/v1/documents/"}[2m])) / '
        'sum(rate(otterworks_db_queries_per_request_count{handler="/api/v1/documents/"}[2m]))'
    )
    assert p95 is not None and p95 > 1, p95
    assert qpr is not None and qpr > 20, qpr


@requires_clear
def test_paged_and_diagnostic_alerts_are_inactive_after_disarm():
    states = _prom_states()
    assert PAGED not in states, states
    assert DIAGNOSTIC not in states, states
    assert not [a for a in _am_alerts() if a["labels"]["alertname"] in {PAGED, DIAGNOSTIC}]


@requires_clear
def test_resolution_goes_to_sink_but_does_not_re_page_devin():
    # devin-oncall is send_resolved: false (one page per incident); the
    # resolved notification is delivered to the `sink` receiver instead.
    assert not [r for r in _devin_pages()
                if r["payload"].get("status") == "resolved"]
    resolved = [
        r for r in _json(f"{SINK_URL}/sink")
        if r["payload"].get("status") == "resolved"
        and any(a["labels"]["alertname"] == DIAGNOSTIC
                for a in r["payload"]["alerts"])
    ]
    assert resolved, "sink receiver never got a resolved notification"
