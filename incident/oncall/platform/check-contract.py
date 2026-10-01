#!/usr/bin/env python3
"""Check chart isolation, dashboard queries, and the storm metric inventory."""

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen

import yaml

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / "infrastructure/helm/document-service"
SOURCE = ROOT / "observability/prometheus/oncall_alerts.yml"
DASHBOARD = ROOT / "observability/grafana/dashboards/oncall-storm.json"
APP_METRICS = {
    "otterworks_db_pool_checked_out",
    "otterworks_db_pool_capacity",
    "otterworks_db_statement_timeouts_total",
    "otterworks_folder_digest_queue_depth",
    "otterworks_folder_digest_oldest_job_age_seconds",
}
POSTGRES_METRICS = {
    "pg_stat_activity_count",
    "pg_stat_activity_max_tx_duration",
    "pg_stat_user_tables_seq_scan",
}
ALERTS = {
    "EdgeErrorRatioHigh": ("web-edge", "critical"),
    "EdgeLatencyP95High": ("web-edge", "warning"),
    "GatewayErrorRatioHigh": ("api-gateway", "critical"),
    "GatewayLatencyP95High": ("api-gateway", "warning"),
    "FolderListLatencyHigh": ("document-service", "critical"),
    "DocumentServiceErrorRateHigh": ("document-service", "critical"),
    "DbPoolSaturated": ("document-service", "warning"),
    "DbStatementTimeouts": ("document-service", "warning"),
    "FolderDigestBacklogGrowing": ("document-service", "warning"),
    "PostgresCPUThrottled": ("postgres", "warning"),
    "PostgresActiveConnectionsHigh": ("postgres", "warning"),
    "PostgresLongRunningQueries": ("postgres", "warning"),
}


def render(namespace: str, enabled: bool, api: bool = True) -> list[dict]:
    command = [
        "helm",
        "template",
        "document-service",
        str(CHART),
        "--namespace",
        namespace,
        "--set",
        "image.tag=contract-check",
        "--set",
        f"monitoring.oncall.enabled={str(enabled).lower()}",
        "--set",
        "monitoring.oncall.dashboard.enabled=true",
        "--set",
        "monitoring.oncall.dashboard.datasourceUid=test-prometheus",
        "--set",
        "monitoring.oncall.p95SloSeconds=0.75",
        "--set",
        "monitoring.links.grafana=https://grafana.example.invalid/",
        "--set",
        "monitoring.rules.extraLabels.branch=demo-oncall-before",
        "--set",
        "monitoring.rules.extraLabels.fix_branch=demo-oncall-after",
        "--set",
        "monitoring.rules.extraLabels.page=incorrect",
        "--set",
        "monitoring.rules.extraLabels.service=incorrect",
        "--set",
        "monitoring.rules.extraLabels.namespace=incorrect",
    ]
    if api:
        command += ["--api-versions", "monitoring.coreos.com/v1"]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return [d for d in yaml.safe_load_all(result.stdout) if d]


def rules_check(rules: dict, directory: Path, filename: str) -> None:
    path = directory / filename
    path.write_text(yaml.safe_dump(rules))
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--entrypoint",
            "/bin/promtool",
            "-v",
            f"{directory}:/rules:ro",
            "prom/prometheus:v3.2.1",
            "check",
            "rules",
            f"/rules/{filename}",
        ],
        check=True,
    )


def check_chart(namespace: str, directory: Path) -> None:
    docs = render(namespace, True)
    rule = next(
        d
        for d in docs
        if d["kind"] == "PrometheusRule" and d["metadata"]["name"] == "document-service-oncall"
    )
    rules = [r for g in rule["spec"]["groups"] for r in g["rules"]]
    assert {r["alert"] for r in rules} == set(ALERTS)
    assert len(rules) == 12
    for item in rules:
        labels = item["labels"]
        assert labels["namespace"] == namespace
        assert labels["page"] == "oncall" and labels["oncall_group"] == "folder-storm"
        assert (labels["service"], labels["severity"]) == ALERTS[item["alert"]]
        assert labels["branch"] == "demo-oncall-before"
        assert labels["fix_branch"] == "demo-oncall-after"
        assert item["for"] in {"1m", "2m", "3m"}
        assert set(item["annotations"]) >= {
            "summary",
            "description",
            "dashboard_url",
            "runbook_url",
        }
        assert item["annotations"]["dashboard_url"] == (
            f"https://grafana.example.invalid/d/oncall-storm?var-namespace={namespace}"
        )
        for metric, selector in re.findall(r"(\w+)\{([^}]*)\}", item["expr"]):
            label = "exported_namespace" if metric.startswith("nginx_") else "namespace"
            assert f'{label}="{namespace}"' in selector, (item["alert"], metric)
        if "Latency" in item["alert"]:
            assert "> 0.75" in item["expr"]
            assert "0.75 seconds" in item["annotations"]["summary"]
    rules_check(rule["spec"], directory, f"{namespace}.yaml")
    cm = next(d for d in docs if d["metadata"]["name"] == "document-service-oncall-dashboard")
    assert cm["metadata"]["labels"]["grafana_dashboard"] == "1"
    dashboard = json.loads(cm["data"]["oncall-storm.json"])
    for panel in dashboard["panels"]:
        datasource = panel.get("datasource", {})
        if datasource.get("type") == "prometheus":
            assert datasource["uid"] == "test-prometheus"
            assert all(t["datasource"]["uid"] == "test-prometheus" for t in panel["targets"])
        elif datasource.get("type") == "loki":
            assert datasource["uid"] == "loki"
    print(f"Chart namespace isolation, labels and dashboard: PASS ({namespace})")


def check_dashboard(directory: Path) -> set[str]:
    dashboard = json.loads(DASHBOARD.read_text())
    assert dashboard["uid"] == "oncall-storm"
    variable = next(v for v in dashboard["templating"]["list"] if v["name"] == "namespace")
    assert variable["current"]["value"] == "otterworks-oncall-before"
    assert variable["regex"] == "/otterworks-oncall-.*/"
    assert dashboard["annotations"]["list"][0]["builtIn"] == 1
    rules = []
    metrics = set()
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            if target["datasource"]["type"] != "prometheus":
                assert target["datasource"]["uid"] == "loki"
                assert target["expr"] == (
                    '{namespace="$namespace", app="document-service"} |= "db_statement_timeout"'
                )
                continue
            expr = target["expr"].replace("$namespace", "otterworks-oncall-before")
            expr = expr.replace("$__rate_interval", "2m")
            metrics.update(re.findall(r"(\w+)\{", expr))
            rules.append(
                {"record": f"oncall_dashboard_panel_{panel['id']}_{target['refId']}", "expr": expr}
            )
    rules_check({"groups": [{"name": "dashboard", "rules": rules}]}, directory, "dashboard.yaml")
    print("Dashboard JSON, namespace variable, datasources and PromQL: PASS")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus", help="Read-only Prometheus HTTP endpoint")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        for namespace in ["otterworks-oncall-before", "otterworks-oncall-after"]:
            check_chart(namespace, directory)
        assert not any(
            d["metadata"]["name"].startswith("document-service-oncall")
            for d in render("otterworks-oncall-before", False)
        )
        assert not any(
            d["kind"] == "PrometheusRule"
            for d in render("otterworks-oncall-before", True, api=False)
        )
        print("Disabled chart and missing Operator API: PASS")
        metrics = check_dashboard(directory)
    source = yaml.safe_load(SOURCE.read_text())
    for group in source["groups"]:
        for rule in group["rules"]:
            metrics.update(re.findall(r"(\w+)\{", rule["expr"]))
    if args.prometheus:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- --prometheus is an operator CLI flag
        with urlopen(
            args.prometheus.rstrip("/") + "/api/v1/label/__name__/values", timeout=30
        ) as r:
            inventory = set(json.load(r)["data"])
        required_live = metrics - APP_METRICS - POSTGRES_METRICS
        assert required_live <= inventory, sorted(required_live - inventory)
        print("Live metric names: " + ", ".join(sorted(required_live)))
    print("Contract app metrics: " + ", ".join(sorted(metrics & APP_METRICS)))
    print("Default postgres-exporter metrics: " + ", ".join(sorted(metrics & POSTGRES_METRICS)))


if __name__ == "__main__":
    main()
