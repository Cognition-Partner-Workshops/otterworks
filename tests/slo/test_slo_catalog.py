import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SLO = ROOT / "observability/slo"
SPEC = importlib.util.spec_from_file_location("collect_baseline", ROOT / "scripts/slo/collect_baseline.py")
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)

CATALOG = yaml.safe_load((SLO / "slo-catalog.yaml").read_text())
JOURNEYS = yaml.safe_load((SLO / "journeys.yaml").read_text())
RULES = yaml.safe_load((ROOT / "observability/prometheus/slo_recording_rules.yml").read_text())
SLIS = {s["id"]: s for s in CATALOG["slis"]}
KINDS = {"availability", "per_route_errors", "latency", "throughput", "saturation",
         "queue_age", "recovery", "worker_errors"}
CORE = {"api-gateway", "auth-service", "file-service", "document-service", "collab-service",
        "notification-service", "search-service", "analytics-service", "admin-service",
        "audit-service", "report-service"}


def gateway_prefixes():
    src = (ROOT / "services/api-gateway/internal/config/config.go").read_text()
    body = src.split("func (c *Config) ServiceRoutes()", 1)[1].split("\n}\n", 1)[0]
    return set(re.findall(r'"(/[^"]+)":', body))


def test_every_sli_is_fully_specified():
    assert len(SLIS) == len(CATALOG["slis"]), "duplicate SLI ids"
    for sli in CATALOG["slis"]:
        assert sli["kind"] in KINDS, sli["id"]
        assert sli["owner"] in CATALOG["owners"], sli["id"]
        assert sli.get("numerator") and sli.get("objective") is not None, sli["id"]
        if sli.get("instrumented") is not True:
            assert sli.get("gap"), f"{sli['id']} is not instrumented and names no gap"
        if isinstance(sli["objective"], float):
            assert 0.9 <= sli["objective"] < 1, sli["id"]
            assert sli.get("denominator"), f"{sli['id']} ratio objective needs a denominator"


def test_every_core_service_has_an_owned_availability_sli():
    covered = {s["service"] for s in CATALOG["slis"] if s["kind"] == "availability"}
    assert CORE - {"api-gateway", "collab-service"} <= covered
    assert {"gw-availability", "collab-connect-errors"} <= SLIS.keys()


def test_every_required_sli_kind_is_defined():
    assert {s["kind"] for s in CATALOG["slis"]} == KINDS


def test_every_gateway_route_prefix_has_an_sli_or_a_recorded_gap():
    gaps = " ".join(s.get("gap", "") for s in CATALOG["slis"])
    routes = " ".join(" ".join(s.get("routes", [])) for s in CATALOG["slis"])
    for prefix in gateway_prefixes():
        leaf = prefix.rstrip("/").rsplit("/", 1)[-1]
        assert prefix in routes or leaf in gaps or prefix in gaps, f"{prefix} has no SLI and no gap"


def test_recording_rules_cover_promql_slis():
    recorded = {r["record"] for g in RULES["groups"] for r in g["rules"]}
    names = {rec.split(":")[1] for rec in recorded}
    for sli in collector.promql_slis(CATALOG):
        if sli["kind"] in {"queue_age", "recovery"} or sli.get("instrumented") is False:
            continue
        assert sli["id"].replace("-", "_") in names, f"no recording rule for {sli['id']}"


def test_prometheus_loads_the_slo_rules():
    cfg = yaml.safe_load((ROOT / "observability/prometheus/prometheus.yml").read_text())
    assert "slo_recording_rules.yml" in cfg["rule_files"]
    assert "slo_recording_rules.yml" in (ROOT / "docker-compose.infra.yml").read_text()


def test_journeys_reference_existing_tests_and_slis():
    defined = {}
    for path in (ROOT / "tests/api").glob("test_*.py"):
        for name in re.findall(r"^def (test_\w+)", path.read_text(), re.M):
            defined[f"tests/api/{path.name}::{name}"] = True
    referenced = set()
    for j in JOURNEYS["journeys"]:
        assert j["owner"] in CATALOG["owners"], j["id"]
        assert j["invariants"], j["id"]
        for sli in j["slis"]:
            assert sli in SLIS, f"{j['id']} references unknown SLI {sli}"
        for t in j["tests"]:
            assert t in defined, f"{j['id']} references missing test {t}"
            referenced.add(t)
    assert referenced == set(defined), f"api tests not mapped to a journey: {set(defined) - referenced}"


@pytest.mark.parametrize("expr,expected", [
    ('sum(rate(x_total{job="a"}[$w]))', 'sum(rate(x_total{namespace="ns",job="a"}[$w]))'),
    ("max(collab_active_connections)", 'max(collab_active_connections{namespace="ns"})'),
    ('histogram_quantile(0.95, sum by (le, path) (rate(b_bucket[5m])))',
     'histogram_quantile(0.95, sum by (le, path) (rate(b_bucket{namespace="ns"}[5m])))'),
])
def test_namespace_scoping(expr, expected):
    assert collector.scope_namespace(expr, "ns") == expected


class FakeProm:
    url = "http://fake"

    def get(self, path, **params):
        if path.endswith("runtimeinfo"):
            return {"storageRetention": "3d"}
        q = params["query"]
        if q.startswith("up{"):
            return {"result": [{"metric": {"job": "auth-service"}, "value": [0, "1"]},
                               {"metric": {"job": "admin-service"}, "value": [0, "0"]}]}
        if "by (job, path)" in q:
            return {"result": [{"metric": {"path": "other"}, "value": [0, "100"]}]}
        if "api_gateway_http_requests_total" in q and "status!~" in q:
            return {"result": [{"metric": {}, "value": [0, "995"]}]}
        if "api_gateway_http_requests_total" in q:
            return {"result": [{"metric": {}, "value": [0, "1000"]}]}
        return {"result": []}

    scalar = collector.Prometheus.scalar
    vector = collector.Prometheus.vector


def test_collect_and_summarize(tmp_path):
    snap = collector.collect(FakeProm(), CATALOG, "otterworks-main", "1d", 1795132800)
    gw = next(s for s in snap["slis"] if s["id"] == "gw-availability")
    assert (gw["numerator"], gw["denominator"], gw["ratio"]) == (995.0, 1000.0, 0.995)
    assert "increase(" in gw["numerator_query"] and 'namespace="otterworks-main"' in gw["numerator_query"]
    assert gw["window"] == "1d" and gw["workload"]
    assert snap["workload"].startswith("health/scrape only")
    assert {"job": "admin-service", "up": False} in snap["targets"]
    (tmp_path / "baseline-2026-11-20-otterworks-main.json").write_text(json.dumps(snap))
    summary = collector.summarize(tmp_path)
    assert summary["days_collected"] == 1 and summary["baseline_complete"] is False
    assert summary["slis"]["gw-availability"]["ratio"] == 0.995


def test_committed_day0_snapshot_is_valid():
    snaps = sorted((SLO / "baseline").glob("baseline-*.json"))
    assert snaps
    snap = json.loads(snaps[0].read_text())
    assert snap["schema"] == 1 and snap["prometheus_retention"]
    assert {s["id"] for s in snap["slis"]} == {s["id"] for s in collector.promql_slis(CATALOG)}
