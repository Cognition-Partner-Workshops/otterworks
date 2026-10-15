"""Unit tests for the incident-responder harness (incident/incident.py).

These are offline: no Compose stack, Redis or Prometheus. They pin the parsing
helpers the verification gate relies on and the consistency between the
scenario catalog, the pinned expectations and the Prometheus alert rules.

Run: uv run --with pytest --with httpx==0.27.2 --with pyyaml==6.0.2 \
         --with PyJWT==2.9.0 --with redis==5.2.1 pytest incident/tests
"""

from __future__ import annotations

import importlib.util
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

HERE = Path(__file__).resolve().parent
INCIDENT_DIR = HERE.parent
REPO = INCIDENT_DIR.parent
ALERT_RULES = REPO / "observability" / "prometheus" / "incident_alerts.yml"
SCENARIOS = ("n-plus-one", "log-flood", "cache-leak", "double-run")
SOAK_METRICS = {"rollup_windows_new", "rollup_duplicates_new"}
REVERSING_STEP = {
    "flag": "unflag",
    "memory-limit": "restore-memory-limit",
    "start-replica": "stop-replica",
    "load": "stop-load",
}
KNOWN_STEPS = {
    "seed",
    "load",
    "stop-load",
    "flag",
    "unflag",
    "restart-document-service",
    "purge-request-log",
    "memory-limit",
    "restore-memory-limit",
    "start-replica",
    "stop-replica",
    "purge-duplicate-rollups",
}


def _load_harness() -> Any:
    spec = importlib.util.spec_from_file_location("incident_harness", INCIDENT_DIR / "incident.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inc = _load_harness()


@pytest.fixture(scope="module")
def cat() -> dict[str, Any]:
    return inc.load_catalog()


@pytest.fixture(scope="module")
def expected() -> dict[str, Any]:
    return inc.load_expected()


@pytest.fixture(scope="module")
def alert_rules() -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load(ALERT_RULES.read_text())
    return {r["alert"]: r for g in doc["groups"] for r in g["rules"] if "alert" in r}


# ---------------------------------------------------------------------------
# catalog / pinned expectations / alert rules agree
# ---------------------------------------------------------------------------


def test_catalog_lists_the_four_scenarios(cat: dict[str, Any]) -> None:
    assert set(cat["scenarios"]) == set(SCENARIOS)


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_scenario_is_pinned_with_the_same_alert(
    name: str, cat: dict[str, Any], expected: dict[str, Any]
) -> None:
    sc = cat["scenarios"][name]
    pinned = expected["scenarios"][name]
    assert pinned["alert"] == sc["alert"]["name"]
    assert pinned["fires_within_seconds"] == sc["alert"]["fires_within_seconds"]


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_scenario_alert_has_a_prometheus_rule(
    name: str, cat: dict[str, Any], alert_rules: dict[str, dict[str, Any]]
) -> None:
    alert = cat["scenarios"][name]["alert"]["name"]
    assert alert in alert_rules
    labels = alert_rules[alert]["labels"]
    assert labels["service"] == "document-service"
    assert labels["scenario"] == name


@pytest.mark.parametrize("name", SCENARIOS)
def test_alert_hold_fits_inside_the_fire_budget(
    name: str, cat: dict[str, Any], alert_rules: dict[str, dict[str, Any]]
) -> None:
    sc = cat["scenarios"][name]
    rule = alert_rules[sc["alert"]["name"]]
    hold = inc.parse_size(rule["for"][:-1]) * {"s": 1, "m": 60}[rule["for"][-1]]
    assert hold < sc["alert"]["fires_within_seconds"]


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_scenario_has_before_and_after_thresholds(name: str, cat: dict[str, Any]) -> None:
    sc = cat["scenarios"][name]
    for phase in ("before", "after"):
        assert sc[phase], f"{name} has no {phase} thresholds"
        for key in sc[phase]:
            metric, bound = key.rsplit("_", 1)
            assert bound in {"min", "max"}, key
            assert metric in inc.METRIC_EXPRS or metric in SOAK_METRICS, (
                f"{key} has neither a Prometheus expression nor a soak measurement"
            )


@pytest.mark.parametrize("name", SCENARIOS)
def test_disarm_reverses_every_arm_flag(name: str, cat: dict[str, Any]) -> None:
    """Whatever arm plants (flag, memory ceiling, replica, load), disarm takes back."""
    sc = cat["scenarios"][name]
    disarm = {inc._step_parts(s) for s in sc["disarm"]}
    for kind, arg in map(inc._step_parts, sc["arm"]):
        if kind in REVERSING_STEP:
            undo = REVERSING_STEP[kind]
            want_arg = arg if kind == "flag" else None
            assert (undo, want_arg) in disarm, f"{name}: arm step {kind} {arg} is never reversed"


@pytest.mark.parametrize("name", SCENARIOS)
@pytest.mark.parametrize("phase", ["arm", "disarm", "after_prepare"])
def test_every_catalog_step_is_known_to_run_step(
    name: str, phase: str, cat: dict[str, Any]
) -> None:
    for step in cat["scenarios"][name].get(phase, []):
        assert inc._step_parts(step)[0] in KNOWN_STEPS


def test_run_step_rejects_unknown_step(cat: dict[str, Any]) -> None:
    with pytest.raises(SystemExit):
        inc.run_step(cat, "n-plus-one", "rm-rf")


def test_double_run_arms_a_replica(cat: dict[str, Any]) -> None:
    kinds = [inc._step_parts(s)[0] for s in cat["scenarios"]["double-run"]["arm"]]
    assert "start-replica" in kinds


def test_fingerprints_match_pinned_before_state(expected: dict[str, Any]) -> None:
    """Golden-app guard: main's document-service source and fixture are the recorded ones."""
    assert inc.fingerprints() == expected["fingerprints"]


def test_targets_default_to_the_local_stack(cat: dict[str, Any], monkeypatch) -> None:
    for env in ("INCIDENT_BASE_URL", "INCIDENT_PROM_URL", "INCIDENT_SINK_URL"):
        monkeypatch.delenv(env, raising=False)
    assert inc.base_url(cat) == "http://localhost:8083"
    assert inc.prom_url(cat) == "http://localhost:9090"
    assert inc.sink_url(cat) == "http://localhost:9095"


def test_target_env_override_strips_trailing_slash(cat: dict[str, Any], monkeypatch) -> None:
    monkeypatch.setenv("INCIDENT_PROM_URL", "http://prom.example:9090/")
    assert inc.prom_url(cat) == "http://prom.example:9090"


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "want"),
    [("512", 512), ("1k", 1024), ("64m", 64 * 1024**2), ("2G", 2 * 1024**3), (" 8b ", 8)],
)
def test_parse_size(spec: str, want: int) -> None:
    assert inc.parse_size(spec) == want


def test_step_parts() -> None:
    assert inc._step_parts("start-replica") == ("start-replica", None)
    assert inc._step_parts({"flag": "chaos:x"}) == ("flag", "chaos:x")


def test_parse_ts_truncates_nanoseconds_and_keeps_utc() -> None:
    ts = inc._parse_ts("2026-10-15T00:53:37.123456789Z")
    assert ts == datetime(2026, 10, 15, 0, 53, 37, 123456, tzinfo=UTC)


def test_parse_ts_naive_is_utc() -> None:
    assert inc._parse_ts("2026-10-15T00:00:00").tzinfo == UTC


@pytest.mark.parametrize(("raw", "want"), [("1", 1.0), ("0.25", 0.25), ("3", 3.0)])
def test_load_scale_accepts_positive(raw: str, want: float, monkeypatch) -> None:
    monkeypatch.setenv("INCIDENT_LOAD_SCALE", raw)
    assert inc.load_scale() == want


@pytest.mark.parametrize("raw", ["0", "-1", "nan", "inf", "abc"])
def test_load_scale_rejects_nonsense(raw: str, monkeypatch) -> None:
    monkeypatch.setenv("INCIDENT_LOAD_SCALE", raw)
    with pytest.raises(SystemExit) as exc:
        inc.load_scale()
    assert exc.value.code == 2


def test_bearer_token_carries_user_id() -> None:
    import jwt

    header = inc.bearer("6d0c5f5e-7f0f-4a4e-9d0c-1a1c1d3a7000")["Authorization"]
    claims = jwt.decode(header.removeprefix("Bearer "), inc.jwt_secret(), algorithms=["HS256"])
    assert claims["user_id"] == claims["sub"] == "6d0c5f5e-7f0f-4a4e-9d0c-1a1c1d3a7000"


def test_threshold_checks_min_max_and_missing_samples() -> None:
    findings: list[str] = []
    inc._threshold_checks(
        findings,
        {"p95_seconds": 2.0, "queries_per_request": 3.0, "request_log_ratio": math.nan},
        {"p95_seconds_min": 1.0, "queries_per_request_max": 5, "request_log_ratio_min": 0.8},
    )
    assert len(findings) == 1
    assert "request_log_ratio" in findings[0] and "no samples" in findings[0]


def test_threshold_checks_reports_breach() -> None:
    findings: list[str] = []
    inc._threshold_checks(findings, {"p95_seconds": 0.2}, {"p95_seconds_min": 1.0})
    assert len(findings) == 1 and findings[0].startswith("p95_seconds=")


def test_check_load_reached_requires_half_the_profile() -> None:
    sc = {"load": {"list": {"rps": 24}}}
    findings: list[str] = []
    inc._check_load_reached(findings, {"request_rate": 12.0}, sc)
    assert findings == []
    inc._check_load_reached(findings, {"request_rate": 11.9}, sc)
    assert len(findings) == 1
    inc._check_load_reached(findings, {"request_rate": None}, sc)
    assert len(findings) == 2


def test_check_load_reached_skips_edit_export_flow() -> None:
    findings: list[str] = []
    inc._check_load_reached(findings, {}, {"load": {"x": {"flow": "edit-then-export"}}})
    assert findings == []


# ---------------------------------------------------------------------------
# Prometheus / sink clients (httpx mocked)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, body: Any, status: int = 200) -> None:
        self._body = body
        self.status_code = status

    def json(self) -> Any:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)  # type: ignore[arg-type]


def _alerts(*alerts: dict[str, Any]) -> dict[str, Any]:
    return {"status": "success", "data": {"alerts": list(alerts)}}


def test_alert_state_prefers_firing(cat: dict[str, Any], monkeypatch) -> None:
    body = _alerts(
        {"labels": {"alertname": "A"}, "state": "pending"},
        {"labels": {"alertname": "A"}, "state": "firing"},
        {"labels": {"alertname": "B"}, "state": "pending"},
    )
    monkeypatch.setattr(inc.httpx, "get", lambda *a, **k: _Resp(body))
    assert inc.alert_state(cat, "A") == "firing"
    assert inc.alert_state(cat, "B") == "pending"
    assert inc.alert_state(cat, "C") == "inactive"


def test_prom_scalar_handles_empty_and_bad_values(cat: dict[str, Any], monkeypatch) -> None:
    results = iter(
        [
            {"status": "success", "data": {"result": []}},
            {"status": "success", "data": {"result": [{"value": [0, "1.5"]}]}},
            {"status": "success", "data": {"result": [{"value": [0, "x"]}]}},
        ]
    )
    monkeypatch.setattr(inc.httpx, "get", lambda *a, **k: _Resp(next(results)))
    assert inc.prom_scalar(cat, "up") is None
    assert inc.prom_scalar(cat, "up") == 1.5
    assert inc.prom_scalar(cat, "up") is None


def test_prom_query_raises_on_error_status(cat: dict[str, Any], monkeypatch) -> None:
    monkeypatch.setattr(inc.httpx, "get", lambda *a, **k: _Resp({"status": "error"}))
    with pytest.raises(RuntimeError):
        inc.prom_query(cat, "up")


def test_alert_fired_at_adds_rule_hold(cat: dict[str, Any], monkeypatch) -> None:
    alerts = _alerts(
        {"labels": {"alertname": "A"}, "state": "firing", "activeAt": "2026-10-15T00:00:00Z"}
    )
    rules = {"data": {"groups": [{"rules": [{"name": "A", "duration": 60}]}]}}

    def fake_get(url: str, *a, **k):
        return _Resp(rules if url.endswith("/rules") else alerts)

    monkeypatch.setattr(inc.httpx, "get", fake_get)
    assert inc.alert_fired_at(cat, "A") == datetime(2026, 10, 15, tzinfo=UTC) + timedelta(
        seconds=60
    )
    assert inc.alert_fired_at(cat, "missing") is None


def _page(alert: str, status: str, at: str) -> dict[str, Any]:
    return {
        "received_at": at,
        "payload": {"status": status, "alerts": [{"labels": {"alertname": alert}}]},
    }


def test_devin_page_for_returns_newest_firing_page(cat: dict[str, Any], monkeypatch) -> None:
    deliveries = [
        _page("A", "firing", "2026-10-15T00:00:00Z"),
        _page("A", "resolved", "2026-10-15T00:05:00Z"),
        _page("A", "firing", "2026-10-15T00:10:00Z"),
    ]
    monkeypatch.setattr(inc.httpx, "get", lambda *a, **k: _Resp(deliveries))
    assert inc.devin_page_for(cat, "A")["received_at"] == "2026-10-15T00:10:00Z"
    assert inc.devin_page_for(cat, "B") is None
    assert inc.devin_page_for(cat, "A", since="2026-10-15T00:11:00Z") is None


def test_devin_page_for_tolerates_sink_down(cat: dict[str, Any], monkeypatch) -> None:
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(inc.httpx, "get", boom)
    assert inc.devin_page_for(cat, "A") is None
    monkeypatch.setattr(inc.httpx, "get", lambda *a, **k: _Resp([], status=503))
    assert inc.devin_page_for(cat, "A") is None
