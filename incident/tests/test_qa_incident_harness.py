"""QA (incidents): harness helpers and the catalog <-> rules <-> routing wiring.

Run with:  uv run --with pytest --with httpx==0.27.2 --with pyyaml==6.0.2 \
               --with PyJWT==2.9.0 --with redis==5.2.1 pytest -q incident/tests
"""

from __future__ import annotations

import importlib.util
import json
import re
from datetime import UTC
from pathlib import Path

import jwt
import pytest
import yaml

HERE = Path(__file__).resolve().parent
INCIDENT_DIR = HERE.parent
REPO = INCIDENT_DIR.parent
OBS = REPO / "observability"

_spec = importlib.util.spec_from_file_location("incident_harness", INCIDENT_DIR / "incident.py")
incident = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(incident)

CATALOG = incident.load_catalog()
RULES = yaml.safe_load((OBS / "prometheus" / "incident_alerts.yml").read_text())
RULE_BY_NAME = {r["alert"]: r for g in RULES["groups"] for r in g["rules"]}
SCENARIOS = sorted(CATALOG["scenarios"])
README = (INCIDENT_DIR / "README.md").read_text()


# ---- pure helpers ---------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "expected"),
    [("256m", 256 * 1024**2), ("512M", 512 * 1024**2), ("1g", 1024**3), ("64k", 64 * 1024),
     ("1024", 1024), (" 2m ", 2 * 1024**2)],
)
def test_parse_size(spec: str, expected: int) -> None:
    assert incident.parse_size(spec) == expected


def test_step_parts_handles_bare_and_keyed_steps() -> None:
    assert incident._step_parts("seed") == ("seed", None)
    assert incident._step_parts({"flag": "k"}) == ("flag", "k")
    assert incident._step_parts({"load": "list"}) == ("load", "list")


def test_parse_ts_truncates_prometheus_nanoseconds() -> None:
    ts = incident._parse_ts("2026-10-14T22:00:00.123456789Z")
    assert ts.tzinfo is not None and ts.microsecond == 123456
    assert incident._parse_ts("2026-10-14T22:00:00").tzinfo == UTC


def test_stats_line_reports_percentiles_queries_and_errors() -> None:
    s = incident.Stats()
    assert s.line() == "no requests"
    for i in range(100):
        s.add(latency=(i + 1) / 100, status=500 if i < 5 else 200, queries=104)
    line = s.line()
    assert "n=100" in line and "queries/req=104.0" in line and "5xx=5.0%" in line
    assert "p95=960ms" in line
    s.reset()
    assert s.total == 0 and s.line() == "no requests"


def test_bearer_signs_a_jwt_for_the_fixture_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "qa-secret")
    owner = CATALOG["seed"]["owner_id"]
    token = incident.bearer(owner)["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(token, "qa-secret", algorithms=["HS256", "HS384"])
    assert owner in (claims.get("sub"), claims.get("user_id"))


def test_target_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INCIDENT_PROM_URL", "http://prom.example:9999/")
    assert incident.prom_url(CATALOG).rstrip("/") == "http://prom.example:9999"
    monkeypatch.delenv("INCIDENT_PROM_URL")
    assert incident.prom_url(CATALOG) == "http://localhost:9090"


def test_load_scale_defaults_to_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INCIDENT_LOAD_SCALE", raising=False)
    assert incident.load_scale() == 1.0


def test_fingerprints_are_stable_and_match_the_recorded_baseline() -> None:
    fp = incident.fingerprints()
    assert fp == incident.fingerprints()
    expected = yaml.safe_load((INCIDENT_DIR / "expected.yaml").read_text())["fingerprints"]
    assert fp["fixture"] == expected["fixture"], "fixture drift vs incident/expected.yaml"


# ---- catalog <-> alert rules ---------------------------------------------


def test_expected_yaml_agrees_with_the_catalog() -> None:
    expected = yaml.safe_load((INCIDENT_DIR / "expected.yaml").read_text())["scenarios"]
    assert sorted(expected) == SCENARIOS
    for name, exp in expected.items():
        alert = CATALOG["scenarios"][name]["alert"]
        assert exp["alert"] == alert["name"]
        assert exp["fires_within_seconds"] == alert["fires_within_seconds"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scenario_alert_is_a_paging_rule_labelled_with_the_scenario(scenario: str) -> None:
    alert = CATALOG["scenarios"][scenario]["alert"]
    rule = RULE_BY_NAME[alert["name"]]
    assert rule["labels"]["page"] == "devin"
    assert rule["labels"]["scenario"] == scenario
    assert rule["labels"]["service"] == "document-service"


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_rule_for_window_fits_inside_the_time_to_fire_promise(scenario: str) -> None:
    alert = CATALOG["scenarios"][scenario]["alert"]
    raw = RULE_BY_NAME[alert["name"]]["for"]
    hold = int(raw[:-1]) * (60 if raw.endswith("m") else 1)
    # Prometheus eval interval 15s + Alertmanager group_wait 10s on top of `for`.
    assert hold + 25 <= alert["fires_within_seconds"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_runbook_anchor_exists_for_each_scenario(scenario: str) -> None:
    rule = RULE_BY_NAME[CATALOG["scenarios"][scenario]["alert"]["name"]]
    url = rule["annotations"].get("runbook_url", "")
    if url:
        assert url.endswith(f"README.md#{scenario}")
    assert f"\n## {scenario}\n" in README


def test_paging_rules_link_the_grafana_dashboard_that_exists() -> None:
    dash = json.loads((OBS / "grafana" / "dashboards" / "incident-responder.json").read_text())
    for name, rule in RULE_BY_NAME.items():
        url = rule["annotations"].get("dashboard_url")
        if rule["labels"].get("page") == "devin":
            assert url, f"{name} has no dashboard_url"
        if url:
            assert url.endswith(f"/d/{dash['uid']}")


def test_alert_exprs_reference_only_metrics_document_service_exports() -> None:
    telemetry_src = (REPO / "services/document-service/app/telemetry.py").read_text()
    for name, rule in RULE_BY_NAME.items():
        metrics = re.findall(r"\b(otterworks_[a-z_]+?)(?:_sum|_count|_bucket)?\b", rule["expr"])
        for metric in metrics:
            base = re.sub(r"_(sum|count|bucket)$", "", metric)
            assert f'"{base}"' in telemetry_src, f"{name} reads unknown metric {base}"


def test_harness_metric_exprs_match_the_list_handler_rule() -> None:
    rule = RULE_BY_NAME["DocumentListLatencyHigh"]["expr"]
    assert 'handler="/api/v1/documents/"' in rule
    assert incident.LIST_HANDLER == "/api/v1/documents/"
    assert incident.LIST_HANDLER in incident.METRIC_EXPRS["p95_seconds"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_disarm_reverses_every_flag_the_arm_sets(scenario: str) -> None:
    sc = CATALOG["scenarios"][scenario]
    armed = {arg for kind, arg in map(incident._step_parts, sc["arm"]) if kind == "flag"}
    cleared = {arg for kind, arg in map(incident._step_parts, sc["disarm"]) if kind == "unflag"}
    assert armed <= cleared
    kinds = {k for k, _ in map(incident._step_parts, sc["arm"])}
    dkinds = {k for k, _ in map(incident._step_parts, sc["disarm"])}
    if "load" in kinds:
        assert "stop-load" in dkinds
    if "start-replica" in kinds:
        assert "stop-replica" in dkinds


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scenario_has_runbook_text_and_thresholds(scenario: str) -> None:
    sc = CATALOG["scenarios"][scenario]
    keys = ("title", "user_sees", "chart_shows", "code_cause", "correct_fix", "before", "after")
    for key in keys:
        assert sc.get(key), f"{scenario} missing {key}"


# ---- prometheus / alertmanager wiring --------------------------------------


def test_prometheus_loads_the_incident_rules_and_scrapes_document_service() -> None:
    prom = yaml.safe_load((OBS / "prometheus" / "prometheus.yml").read_text())
    assert "incident_alerts.yml" in " ".join(prom["rule_files"])
    jobs = {j["job_name"] for j in prom["scrape_configs"]}
    assert "document-service" in jobs
    am = json.dumps(prom.get("alerting", {}))
    assert "alertmanager:9093" in am


def test_alertmanager_routes_page_devin_to_devin_and_slack() -> None:
    raw = (OBS / "alertmanager" / "alertmanager.yml.tmpl").read_text()
    cfg = yaml.safe_load(raw)
    routes = cfg["route"]["routes"]
    receivers = [r["receiver"] for r in routes if "page = devin" in r["matchers"]]
    assert receivers == ["devin-oncall", "slack-oncall"]
    assert routes[0].get("continue") is True
    assert cfg["route"]["receiver"] == "sink"
    by_name = {r["name"]: r for r in cfg["receivers"]}
    devin_urls = [w["url"] for w in by_name["devin-oncall"]["webhook_configs"]]
    assert "http://alert-sink:9095/devin" in devin_urls
    assert by_name["sink"]["webhook_configs"][0]["send_resolved"] is True


def test_sink_url_targets_loopback() -> None:
    assert incident.sink_url(CATALOG).startswith("http://localhost:9095")
