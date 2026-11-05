"""Render the document-service chart per tenant the way deploy-tenant.sh does.

The tenant id comes from the branch through scripts/lib/tenant-common.sh, the
overlay from infrastructure/helm/tenant-values/<id>/document-service.yaml, and
the `branch` label from --set-string, so each case is the helm invocation a
CD deploy of that branch would run (minus the cluster).

    uv run --with pyyaml==6.0.2 --with pytest==8.3.5 \
        pytest infrastructure/helm/tests
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from functools import cache
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
CHART = REPO / "infrastructure/helm/document-service"
TENANT_VALUES = REPO / "infrastructure/helm/tenant-values"
ALERTS_SRC = REPO / "observability/prometheus/incident_alerts.yml"
DASHBOARD_SRC = REPO / "observability/grafana/dashboards/incident-responder.json"

pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="helm not installed")


def tenant_id(branch: str) -> str:
    out = subprocess.run(
        ["bash", "-c", 'source scripts/lib/tenant-common.sh && branch_tenant_id "$1"', "_", branch],
        cwd=REPO,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


@cache
def render(branch: str) -> dict[tuple[str, str], dict]:
    tid = tenant_id(branch)
    args = [
        "helm", "template", "document-service", str(CHART),
        "--namespace", f"otterworks-{tid}",
        "--api-versions", "monitoring.coreos.com/v1",
        "--set", "image.tag=ci",
        "--set-string", f"monitoring.rules.extraLabels.branch={branch}",
    ]  # fmt: skip
    overlay = TENANT_VALUES / tid / "document-service.yaml"
    if overlay.is_file():
        args += ["-f", str(overlay)]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    docs = [d for d in yaml.safe_load_all(out) if d]
    return {(d["kind"], d["metadata"]["name"]): d for d in docs}


def rules(branch: str) -> list[dict]:
    rule = render(branch)[("PrometheusRule", "document-service-incident")]
    return [r for g in rule["spec"]["groups"] for r in g["rules"]]


def dashboard(branch: str) -> dict:
    cm = render(branch)[("ConfigMap", "document-service-incident-dashboard")]
    return json.loads(cm["data"]["incident-responder.json"])


def unscope(expr: str, ns: str) -> str:
    return expr.replace(f'{{namespace="{ns}"}}', "").replace(f'namespace="{ns}", ', "")


SOURCE_RULES = [r for g in yaml.safe_load(ALERTS_SRC.read_text())["groups"] for r in g["rules"]]
PAGED = {r["alert"] for r in SOURCE_RULES if r.get("labels", {}).get("page") == "devin"}


def test_demo_bank_resolves_to_bank_tenant():
    assert tenant_id("demo-bank") == "bank"


def test_bank_gets_its_own_alerts_scoped_to_its_namespace():
    ns = "otterworks-bank"
    rendered = rules("demo-bank")
    assert [r["alert"] for r in rendered] == [r["alert"] for r in SOURCE_RULES]
    for src, r in zip(SOURCE_RULES, rendered, strict=True):
        assert r["labels"]["namespace"] == ns
        assert r["labels"]["branch"] == "demo-bank"
        assert "fix_branch" not in r["labels"]
        assert r["labels"].get("page") == src.get("labels", {}).get("page")
        assert r.get("for") == src.get("for")
        assert set(re.findall(r'namespace="([^"]+)"', r["expr"])) == {ns}
        assert unscope(r["expr"], ns) == src["expr"], "alert expression/threshold changed"
    assert {r["alert"] for r in rendered if r["labels"].get("page") == "devin"} == PAGED
    assert "DocumentListLatencyHigh" in PAGED


def test_bank_gets_its_own_dashboard():
    d = dashboard("demo-bank")
    src = json.loads(DASHBOARD_SRC.read_text())
    assert d["uid"] == "ir-otterworks-bank"
    assert d["title"] == f"{src['title']} (otterworks-bank)"
    exprs = [t["expr"] for p in d["panels"] for t in p.get("targets", []) if "expr" in t]
    assert exprs
    for e in exprs:
        assert set(re.findall(r'namespace="([^"]+)"', e)) == {"otterworks-bank"}
    rule_links = {r["annotations"].get("dashboard_url") for r in rules("demo-bank")} - {None}
    assert rule_links == {"https://grafana.otterworks.app/d/ir-otterworks-bank"}


@pytest.mark.parametrize(
    ("branch", "ns", "fix_branch"),
    [("main", "otterworks-main", "demo-incident"), ("demo-incident", "otterworks-incident", None)],
)
def test_existing_incident_tenants_unchanged(branch, ns, fix_branch):
    for r in rules(branch):
        assert r["labels"]["namespace"] == ns
        assert r["labels"].get("fix_branch") == fix_branch
        assert set(re.findall(r'namespace="([^"]+)"', r["expr"])) == {ns}
    assert dashboard(branch)["uid"] == f"ir-{ns}"


def test_bank_renders_exactly_like_the_incident_tenant_but_in_its_namespace():
    def normalise(branch: str, ns: str) -> str:
        docs = render(branch)
        keep = {
            f"{k}/{n}": v
            for (k, n), v in docs.items()
            if k in ("PrometheusRule", "ConfigMap", "Deployment")
        }
        return json.dumps(keep, sort_keys=True).replace(ns, "<ns>").replace(branch, "<branch>")

    assert normalise("demo-bank", "otterworks-bank") == normalise(
        "demo-incident", "otterworks-incident"
    )


@pytest.mark.parametrize("branch", ["workshop-someone", "demo-cpg"])
def test_tenants_without_an_overlay_get_no_incident_resources(branch):
    kinds = set(render(branch))
    assert ("PrometheusRule", "document-service-incident") not in kinds
    assert ("ConfigMap", "document-service-incident-dashboard") not in kinds
