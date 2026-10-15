"""Unit tests for the incident-responder harness (incident/incident.py).

Pure checks only: no Docker, Prometheus or Redis. They pin the contract between
incident/scenarios.yaml, incident/expected.yaml, the Prometheus alert rules, the
Alertmanager routing template, the runbook and document-service's chaos flags,
and exercise the harness helpers with fakes.

    uv run --with pytest --with httpx==0.27.2 --with pyyaml==6.0.2 \
        --with PyJWT==2.9.0 --with redis==5.2.1 pytest incident/tests -q
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "incident_harness", REPO / "incident" / "incident.py"
)
assert _spec and _spec.loader
inc = importlib.util.module_from_spec(_spec)
sys.modules["incident_harness"] = inc
_spec.loader.exec_module(inc)

SCENARIO_NAMES = ("n-plus-one", "log-flood", "cache-leak", "double-run")


@pytest.fixture(scope="module")
def catalog() -> dict[str, Any]:
    return inc.load_catalog()


@pytest.fixture(scope="module")
def expected() -> dict[str, Any]:
    return inc.load_expected()


@pytest.fixture(scope="module")
def alert_rules() -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load((REPO / "observability/prometheus/incident_alerts.yml").read_text())
    return {r["alert"]: r for g in doc["groups"] for r in g["rules"]}


def _seconds(duration: str) -> float:
    m = re.fullmatch(r"(\d+)([smh])", duration)
    assert m, duration
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600}[m.group(2)]


# ---------------------------------------------------------------------------
# catalog / expected / rules contract
# ---------------------------------------------------------------------------


def test_catalog_lists_the_four_documented_scenarios(catalog: dict[str, Any]) -> None:
    assert tuple(catalog["scenarios"]) == SCENARIO_NAMES


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_scenario_has_required_fields(catalog: dict[str, Any], name: str) -> None:
    sc = catalog["scenarios"][name]
    for key in ("title", "user_sees", "chart_shows", "code_cause", "correct_fix", "arm", "disarm"):
        assert sc.get(key), f"{name} missing {key}"
    alert = sc["alert"]
    assert alert["fires_within_seconds"] > 0
    assert alert["resolves_within_seconds"] > 0
    assert sc["before"], f"{name} has no before-gate thresholds"
    assert sc["after"], f"{name} has no after-gate thresholds"
    for key in [*sc["before"], *sc["after"]]:
        assert key.rsplit("_", 1)[1] in {"min", "max"}, key


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_expected_pins_every_scenario_alert(
    catalog: dict[str, Any], expected: dict[str, Any], name: str
) -> None:
    sc = catalog["scenarios"][name]
    pinned = expected["scenarios"][name]
    assert pinned["alert"] == sc["alert"]["name"]
    assert pinned["fires_within_seconds"] == sc["alert"]["fires_within_seconds"]


def test_fixture_and_source_fingerprints_match_recorded_before_state(
    expected: dict[str, Any],
) -> None:
    assert inc.fingerprints() == expected["fingerprints"]


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_scenario_alert_is_a_paging_rule_for_that_scenario(
    catalog: dict[str, Any], alert_rules: dict[str, dict[str, Any]], name: str
) -> None:
    sc = catalog["scenarios"][name]
    rule = alert_rules[sc["alert"]["name"]]
    assert rule["labels"]["page"] == "devin"
    assert rule["labels"]["service"] == "document-service"
    assert rule["labels"]["scenario"] == name
    assert rule["annotations"]["runbook_url"].endswith(f"incident/README.md#{name}")
    # The alert has to be able to fire inside its promise: `for` plus one
    # evaluation interval plus Alertmanager group_wait must fit the budget.
    assert _seconds(rule["for"]) + 15 + 10 <= sc["alert"]["fires_within_seconds"]


def test_diagnostic_fanout_rule_does_not_page(alert_rules: dict[str, dict[str, Any]]) -> None:
    assert "page" not in alert_rules["DocumentListQueryFanout"]["labels"]


def test_every_paging_rule_has_runbook_and_dashboard(
    alert_rules: dict[str, dict[str, Any]],
) -> None:
    paging = {n: r for n, r in alert_rules.items() if r["labels"].get("page") == "devin"}
    assert len(paging) == 5
    for name, rule in paging.items():
        assert rule["annotations"].get("runbook_url"), name
        assert rule["annotations"]["dashboard_url"].endswith("/d/otterworks-incident-responder")


def test_harness_metric_exprs_reference_exported_metrics() -> None:
    telemetry = (REPO / "services/document-service/app/telemetry.py").read_text()
    for key, expr in inc.METRIC_EXPRS.items():
        for metric in re.findall(r"(otterworks_[a-z_]+?)(?:_sum|_count|_bucket)?\b", expr):
            base = re.sub(r"_(sum|count|bucket)$", "", metric)
            assert f'"{base}"' in telemetry, f"{key}: {base} not exported by document-service"


def test_rules_file_is_loaded_by_prometheus() -> None:
    prom = yaml.safe_load((REPO / "observability/prometheus/prometheus.yml").read_text())
    assert "incident_alerts.yml" in prom["rule_files"]
    jobs = {j["job_name"] for j in prom["scrape_configs"]}
    assert "document-service" in jobs


def test_alertmanager_routes_pages_to_devin_and_slack() -> None:
    am = yaml.safe_load((REPO / "observability/alertmanager/alertmanager.yml.tmpl").read_text())
    routes = am["route"]["routes"]
    receivers = [r["receiver"] for r in routes if r["matchers"] == ["page = devin"]]
    assert receivers == ["devin-oncall", "slack-oncall"]
    assert routes[0].get("continue") is True
    devin = next(r for r in am["receivers"] if r["name"] == "devin-oncall")
    assert devin["webhook_configs"][0]["url"] == "http://alert-sink:9095/devin"


def test_runbook_table_lists_every_alert(
    catalog: dict[str, Any], alert_rules: dict[str, dict[str, Any]]
) -> None:
    readme = (REPO / "incident/README.md").read_text()
    for name, sc in catalog["scenarios"].items():
        assert f"## {name}" in readme
        row = next(line for line in readme.splitlines() if f"`{sc['alert']['name']}`" in line)
        assert f"{sc['alert']['fires_within_seconds']} s" in row


def test_chaos_flags_match_document_service_constants(catalog: dict[str, Any]) -> None:
    chaos_src = (REPO / "services/document-service/app/chaos.py").read_text()
    consts = set(re.findall(r'"(chaos:document-service:[a-z_]+)"', chaos_src))
    used: set[str] = set()
    for sc in catalog["scenarios"].values():
        for step in sc["arm"]:
            kind, arg = inc._step_parts(step)
            if kind == "flag":
                used.add(arg)
    assert used and used <= consts


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_disarm_reverses_every_arm_step(catalog: dict[str, Any], name: str) -> None:
    sc = catalog["scenarios"][name]
    disarm = [inc._step_parts(s) for s in sc["disarm"]]
    for step in sc["arm"]:
        kind, arg = inc._step_parts(step)
        match kind:
            case "flag":
                assert ("unflag", arg) in disarm
            case "load":
                assert ("stop-load", None) in disarm
            case "memory-limit":
                assert ("restore-memory-limit", None) in disarm
            case "start-replica":
                assert ("stop-replica", None) in disarm
            case "seed":
                pass
            case _:
                pytest.fail(f"unknown arm step {kind}")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "want"),
    [("256m", 256 * 1024**2), ("512M", 512 * 1024**2), ("1g", 1024**3), ("64k", 65536), ("10", 10)],
)
def test_parse_size(spec: str, want: int) -> None:
    assert inc.parse_size(spec) == want


def test_step_parts() -> None:
    assert inc._step_parts("seed") == ("seed", None)
    assert inc._step_parts({"flag": "k"}) == ("flag", "k")


def test_parse_ts_truncates_prometheus_nanoseconds() -> None:
    ts = inc._parse_ts("2026-10-15T04:37:00.123456789Z")
    assert ts == datetime(2026, 10, 15, 4, 37, 0, 123456, tzinfo=UTC)
    assert inc._parse_ts("2026-10-15T04:37:00").tzinfo is UTC


@pytest.mark.parametrize("raw", ["0", "-1", "nan", "inf", "abc"])
def test_load_scale_rejects_non_positive_or_non_finite(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("INCIDENT_LOAD_SCALE", raw)
    with pytest.raises(SystemExit) as exc:
        inc.load_scale()
    assert exc.value.code == 2


def test_load_scale_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INCIDENT_LOAD_SCALE", raising=False)
    assert inc.load_scale() == 1.0
    monkeypatch.setenv("INCIDENT_LOAD_SCALE", "0.5")
    assert inc.load_scale() == 0.5


def test_targets_are_overridable_by_env(
    monkeypatch: pytest.MonkeyPatch, catalog: dict[str, Any]
) -> None:
    assert inc.base_url(catalog) == "http://localhost:8083"
    monkeypatch.setenv("INCIDENT_BASE_URL", "http://tenant.example/")
    monkeypatch.setenv("INCIDENT_PROM_URL", "http://prom.example/")
    assert inc.base_url(catalog) == "http://tenant.example"
    assert inc.prom_url(catalog) == "http://prom.example"


def test_bearer_token_carries_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    import secrets

    import jwt

    secret = secrets.token_hex(32)
    monkeypatch.setenv("JWT_SECRET", secret)
    header = inc.bearer("6d0c5f5e-7f0f-4a4e-9d0c-1a1c1d3a7000")["Authorization"]
    claims = jwt.decode(header.removeprefix("Bearer "), secret, algorithms=["HS256"])
    assert claims["sub"] == claims["user_id"] == "6d0c5f5e-7f0f-4a4e-9d0c-1a1c1d3a7000"


def test_threshold_checks_min_max_and_missing_samples() -> None:
    findings: list[str] = []
    inc._threshold_checks(
        findings,
        {"queries_per_request": 104.0, "p95_seconds": 0.2, "cache_entries": None},
        {"queries_per_request_min": 50, "p95_seconds_min": 1.0, "cache_entries_min": 2000},
    )
    assert len(findings) == 2
    assert findings[0].startswith("p95_seconds=0.200 >= 1.0")
    assert "no samples" in findings[1]


def test_check_load_reached_requires_half_the_profile(catalog: dict[str, Any]) -> None:
    sc = catalog["scenarios"]["n-plus-one"]
    ok: list[str] = []
    inc._check_load_reached(ok, {"request_rate": 12.0}, sc)
    assert ok == []
    low: list[str] = []
    inc._check_load_reached(low, {"request_rate": 11.9}, sc)
    assert len(low) == 1
    skipped: list[str] = []
    inc._check_load_reached(skipped, {}, catalog["scenarios"]["cache-leak"])
    assert skipped == []


def test_arm_conditions_reflect_live_state(
    monkeypatch: pytest.MonkeyPatch, catalog: dict[str, Any]
) -> None:
    monkeypatch.setattr(inc, "flag_is_set", lambda cat, key: True)
    monkeypatch.setattr(inc, "container_memory_limit", lambda svc: 256 * 1024**2)
    monkeypatch.setattr(inc, "container_running", lambda svc: False)
    leak = inc.arm_conditions(catalog, catalog["scenarios"]["cache-leak"])
    assert [holds for _, holds in leak] == [True, True]
    double = inc.arm_conditions(catalog, catalog["scenarios"]["double-run"])
    assert double == [("document-service-replica is running", False)]
    assert inc.arm_conditions(catalog, catalog["scenarios"]["n-plus-one"]) == []


def test_run_step_dispatches_every_catalog_step(
    monkeypatch: pytest.MonkeyPatch, catalog: dict[str, Any]
) -> None:
    calls: list[tuple[str, ...]] = []

    async def fake_seed(cat: dict[str, Any]) -> dict[str, int]:
        calls.append(("seed",))
        return {}

    monkeypatch.setattr(inc, "seed", fake_seed)
    monkeypatch.setattr(inc, "start_background_load", lambda s: calls.append(("load", s)))
    monkeypatch.setattr(inc, "stop_background_load", lambda: calls.append(("stop-load",)))
    monkeypatch.setattr(inc, "set_flag", lambda c, k, on: calls.append(("flag", k, str(on))))
    monkeypatch.setattr(inc, "purge_request_log", lambda c: calls.append(("purge",)))
    monkeypatch.setattr(
        inc, "recreate_document_service", lambda c, m: calls.append(("mem", str(m)))
    )
    monkeypatch.setattr(inc, "compose", lambda *a, **k: calls.append(("compose", *a)))
    monkeypatch.setattr(inc, "wait_healthy", lambda c: None)
    for name, sc in catalog["scenarios"].items():
        for step in [*sc["arm"], *sc["disarm"], *sc.get("after_prepare", [])]:
            inc.run_step(catalog, name, step)
    assert ("flag", "chaos:document-service:render_cache", "True") in calls
    assert ("flag", "chaos:document-service:request_log", "False") in calls
    assert ("mem", "256m") in calls and ("mem", "None") in calls
    assert any(c[:2] == ("compose", "--profile") and "document-service-replica" in c for c in calls)


def test_run_step_rejects_unknown_step(catalog: dict[str, Any]) -> None:
    with pytest.raises(SystemExit):
        inc.run_step(catalog, "n-plus-one", "drop-database")


class _FakeResponse:
    def __init__(self, status: int, body: Any) -> None:
        self.status_code = status
        self._body = body

    def json(self) -> Any:
        return self._body


def _delivery(received_at: str, status: str, alertname: str) -> dict[str, Any]:
    return {
        "received_at": received_at,
        "payload": {"status": status, "alerts": [{"labels": {"alertname": alertname}}]},
    }


def test_devin_page_for_picks_newest_fresh_firing_delivery(
    monkeypatch: pytest.MonkeyPatch, catalog: dict[str, Any]
) -> None:
    deliveries = [
        _delivery("2026-10-15T04:00:00Z", "firing", "DocumentListLatencyHigh"),
        _delivery("2026-10-15T04:40:00Z", "resolved", "DocumentListLatencyHigh"),
        _delivery("2026-10-15T04:41:00Z", "firing", "RequestLogVolumeNearFull"),
    ]
    monkeypatch.setattr(inc.httpx, "get", lambda *a, **k: _FakeResponse(200, deliveries))
    stale = inc.devin_page_for(catalog, "DocumentListLatencyHigh", since="2026-10-15T04:30:00Z")
    assert stale is None
    old = inc.devin_page_for(catalog, "DocumentListLatencyHigh")
    assert old is deliveries[0]
    assert inc.devin_page_for(catalog, "RequestLogVolumeNearFull") is deliveries[2]


def test_devin_page_for_tolerates_unreachable_sink(
    monkeypatch: pytest.MonkeyPatch, catalog: dict[str, Any]
) -> None:
    def boom(*a: Any, **k: Any) -> Any:
        raise inc.httpx.ConnectError("refused")

    monkeypatch.setattr(inc.httpx, "get", boom)
    assert inc.devin_page_for(catalog, "DocumentListLatencyHigh") is None


def test_verify_refuses_after_gate_on_unchanged_source() -> None:
    before = set(inc.REPORT_DIR.glob("n-plus-one-after-*.json"))
    args = argparse.Namespace(scenario="n-plus-one", expect="after", soak=None, keep_going=False)
    with pytest.raises(SystemExit) as exc:
        inc.cmd_verify(args)
    assert exc.value.code == 1
    reports = set(inc.REPORT_DIR.glob("n-plus-one-after-*.json")) - before
    try:
        assert reports, "a red gate must still write its report"
        assert all("source fingerprint differs" in r.read_text() for r in reports)
    finally:
        for r in reports:
            r.unlink()
