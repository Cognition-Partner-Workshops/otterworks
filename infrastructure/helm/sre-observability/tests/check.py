"""Render and test routing boundaries, idle tenants and representative rule behavior."""
import pathlib
import subprocess
import tempfile

import yaml


CHART = pathlib.Path(__file__).resolve().parents[1]


def render(*args):
    return list(yaml.safe_load_all(subprocess.check_output(
        ["helm", "template", "sre-observability", str(CHART), "-n", "monitoring", *args],
        text=True,
    )))


docs = [d for d in render() if d]
assert not any(d["kind"] in ("Secret", "AlertmanagerConfig", "Service", "ServiceMonitor") for d in docs)
blocked = subprocess.run(
    ["helm", "template", "sre-observability", str(CHART), "-n", "monitoring", "--set", "alerting.webhook.enabled=true"],
    capture_output=True, text=True,
)
assert blocked.returncode != 0 and "Bearer-to-X-Webhook-Secret relay" in blocked.stderr
enabled = [d for d in render("--set", "alerting.webhook.enabled=true", "--set", "alerting.webhook.headerRelay=true") if d]
config = next(d for d in enabled if d["kind"] == "AlertmanagerConfig")
assert config["spec"]["route"]["groupBy"] == ["alertname", "affected_namespace"]
receiver = config["spec"]["receivers"][0]["webhookConfigs"][0]
assert receiver["sendResolved"] is True and receiver["urlSecret"]["key"] == "url"
assert receiver["httpConfig"]["authorization"]["credentials"]["key"] == "webhook-secret"
for doc in docs:
    for rule in doc.get("rules", []):
        assert set(rule["verbs"]) <= {"get", "list", "watch"}
        assert "secrets" not in rule["resources"]
        assert "pods/exec" not in rule["resources"]
        if "services/proxy" in rule["resources"]:
            assert doc["kind"] == "Role" and len(rule["resourceNames"]) == 4
rules = next(d["spec"] for d in docs if d["kind"] == "PrometheusRule")
by_name = {r["alert"]: r for g in rules["groups"] for r in g["rules"]}
assert len(by_name) == 12
# PR #3297 owns otterworks-reliability SLO/capacity/ingress, node readiness and OOM alerts.
assert not {"SREPodOOMKilled", "SRENodeNotReady", "SREIngress5xxHigh", "SREIngressLatencyHigh"} & by_name.keys()
for rule in by_name.values():
    assert rule["labels"]["namespace"] == "monitoring"
    assert rule["labels"]["team"] == "sre" and "page" not in rule["labels"]
    assert rule["expr"].startswith("label_replace(")
    assert {"summary", "description", "runbook_url", "affected_namespace"} <= rule["annotations"].keys()


def expected(name, extra):
    rule = by_name[name]
    labels = dict(rule["labels"], **extra)
    annotations = dict(rule["annotations"], affected_namespace=labels["affected_namespace"])
    return {"exp_labels": labels, "exp_annotations": annotations}


series = [
    {"series": 'prometheus_notifications_errors_total{namespace="monitoring",job="prometheus"}', "values": "0x20"},
    {"series": 'prometheus_notifications_dropped_total{namespace="monitoring",job="prometheus"}', "values": "0x20"},
    {"series": 'up{namespace="otterworks-main",job="document-service",instance="doc"}', "values": "0x20"},
    {"series": 'kube_deployment_spec_replicas{namespace="otterworks-idle",deployment="web-app"}', "values": "0x20"},
    {"series": 'kube_deployment_status_replicas_available{namespace="otterworks-idle",deployment="web-app"}', "values": "0x20"},
    {"series": 'kube_pod_status_ready{namespace="otterworks-main",pod="done",condition="true"}', "values": "0x20"},
    {"series": 'kube_pod_status_phase{namespace="otterworks-main",pod="done",phase="Succeeded"}', "values": "1x20"},
]
checks = [
    {"eval_time": "15m", "alertname": "SREAppTargetDown", "exp_alerts": [expected("SREAppTargetDown", {"affected_namespace": "otterworks-main", "job": "document-service", "instance": "doc"})]},
    {"eval_time": "15m", "alertname": "SRELogShippingUnavailable", "exp_alerts": [expected("SRELogShippingUnavailable", {"affected_namespace": "otterworks-system", "daemonset": "aws-for-fluent-bit"})]},
    *[{"eval_time": "15m", "alertname": name, "exp_alerts": []} for name in ["SREDeploymentUnavailable", "SREPodNotReady"]],
]
with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory)
    (path / "rules.yml").write_text(yaml.safe_dump(rules))
    healthy = [
        {"series": 'kube_daemonset_status_desired_number_scheduled{namespace="otterworks-system",daemonset="aws-for-fluent-bit"}', "values": "3x20"},
        {"series": 'kube_daemonset_status_number_available{namespace="otterworks-system",daemonset="aws-for-fluent-bit"}', "values": "3x20"},
    ]
    suite = {"rule_files": [str(path / "rules.yml")], "evaluation_interval": "1m", "tests": [
        {"interval": "1m", "input_series": series, "alert_rule_test": checks},
        {"interval": "1m", "input_series": healthy, "alert_rule_test": [
            {"eval_time": "15m", "alertname": name, "exp_alerts": []}
            for name in by_name
        ]},
    ]}
    for namespace, deployment, available, fires in [
        ("otterworks-main", "api-gateway", 0, False),
        ("otterworks-main", "auth-service", 0, False),
        ("otterworks-main", "document-service", 0, False),
        ("otterworks-main", "file-service", 0, False),
        ("otterworks-main", "web-app", 0, False),
        ("otterworks-main", "api-gateway", 1, True),
        ("otterworks-main", "admin-service", 0, True),
        ("otterworks-demo", "api-gateway", 0, True),
    ]:
        labels = f'namespace="{namespace}",deployment="{deployment}"'
        suite["tests"].append({
            "interval": "1m",
            "input_series": [
                {"series": f"kube_deployment_spec_replicas{{{labels}}}", "values": "2x20"},
                {"series": f"kube_deployment_status_replicas_available{{{labels}}}", "values": f"{available}x20"},
            ],
            "alert_rule_test": [{
                "eval_time": "15m", "alertname": "SREDeploymentUnavailable",
                "exp_alerts": [expected("SREDeploymentUnavailable", {
                    "affected_namespace": namespace, "deployment": deployment,
                })] if fires else [],
            }],
        })
    (path / "tests.yml").write_text(yaml.safe_dump(suite))
    subprocess.run(["promtool", "check", "rules", str(path / "rules.yml")], check=True)
    subprocess.run(["promtool", "test", "rules", str(path / "tests.yml")], check=True)
print(f"PASS: {len(by_name)} rule label boundaries, webhook opt-in, read-only RBAC, target-down/missing shipping, idle/healthy/empty telemetry and deployment ownership cases")
