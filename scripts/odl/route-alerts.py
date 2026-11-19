#!/usr/bin/env python3
"""Add isolated ODL paging without changing existing routes or receivers."""

import base64
import copy
import difflib
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import yaml

RUN_TOKEN = "odl-1795112287"
CONFIG_SECRET = "alertmanager-odl-config"
WEBHOOK_SECRET = "alertmanager-odl-devin-webhook"
PAGERDUTY_SECRET = "alertmanager-odl-pagerduty"
URL_FILE = f"/etc/alertmanager/secrets/{WEBHOOK_SECRET}/url"
HEADER_FILE = f"/etc/alertmanager/secrets/{WEBHOOK_SECRET}/secret"
RECEIVER = "odl-devin-oncall"
KEY_FILE = f"/etc/alertmanager/secrets/{PAGERDUTY_SECRET}/routing_key"
EVENTS_URL = "http://pagerduty.odl-mocks.svc.cluster.local:8080/v2/enqueue"


def kubectl(*args):
    return json.loads(subprocess.check_output(["kubectl", "-n", "monitoring", *args, "-o", "json"]))


def secret(name, values):
    return {"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
            "metadata": {"namespace": "monitoring", "name": name,
                         "labels": {"run_token": RUN_TOKEN}},
            "data": {k: base64.b64encode(v.encode()).decode() for k, v in values.items()}}


def write_secret(obj, create=False):
    command = ["kubectl", "-n", "monitoring"]
    command += (["create", "-f", "-"] if create else
                ["patch", "secret", obj["metadata"]["name"], "--type=merge", "--patch-file=/dev/stdin"])
    result = subprocess.run(command,
                            input=json.dumps(obj), text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Secret write failed (kubectl exit {result.returncode}); output withheld")


def ensure_webhook_secret():
    values = {key: os.environ.get(env) for key, env in (
        ("url", "DEVIN_ALERT_WEBHOOK_URL"), ("secret", "DEVIN_ALERT_WEBHOOK_SECRET"))}
    if any(value is not None for value in values.values()) and not all(values.values()):
        raise ValueError("Both DEVIN_ALERT_WEBHOOK_URL and DEVIN_ALERT_WEBHOOK_SECRET are required")
    current = subprocess.check_output(["kubectl", "-n", "monitoring", "get", "secret", WEBHOOK_SECRET,
                                       "--ignore-not-found", "-o", "json"], text=True)
    obj = json.loads(current) if current.strip() else None
    if not any(values.values()):
        if obj is None:
            raise ValueError("Webhook Secret is absent; supply both DEVIN_ALERT_WEBHOOK environment variables")
        try:
            values = {key: base64.b64decode((obj.get("data") or {}).get(key, ""), validate=True).decode()
                      for key in values}
        except (ValueError, TypeError):
            raise ValueError("Existing webhook Secret has invalid encoded credentials") from None
    try:
        target = urlsplit(values["url"] or "")
        valid = (target.scheme == "https" and target.hostname and not target.username
                 and not target.password and all(values.values())
                 and all("\r" not in value and "\n" not in value for value in values.values()))
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Webhook requires an HTTPS URL and nonempty credentials without newlines")
    desired = secret(WEBHOOK_SECRET, values)
    if obj is None:
        write_secret(desired, create=True)
    else:
        updated = copy.deepcopy(obj)
        updated.setdefault("data", {}).update(desired["data"])
        updated["metadata"].setdefault("labels", {}).update(desired["metadata"]["labels"])
        if updated != obj:
            write_secret(updated)


def pagerduty_routing_key():
    key = subprocess.check_output([
        "kubectl", "-n", "odl-mocks", "exec", "deployment/pagerduty", "--", "python", "-c",
        "import app; print(app.get('services', 'PSVC001')['integrations'][0]['integration_key'])"
    ], text=True).strip()
    if not key:
        raise ValueError("Seeded PagerDuty service has no routing key")
    return key


def updated_config(config):
    updated = copy.deepcopy(config)
    receivers = [r for r in updated.get("receivers", []) if r["name"] == "devin-oncall"]
    routes = updated.get("route", {}).get("routes", [])
    oncall_routes = [r for r in routes if r.get("receiver") == "devin-oncall"]
    if len(receivers) != 1 or len(oncall_routes) != 1:
        raise ValueError("Expected exactly one top-level devin-oncall route and receiver")
    integrations = [p for p in receivers[0].get("pagerduty_configs", []) if p.get("url") == EVENTS_URL]
    if len(integrations) != 1:
        raise ValueError("Expected exactly one existing ODL PagerDuty Events v2 integration")
    receiver = {"name": RECEIVER, "webhook_configs": [{
        "url_file": URL_FILE, "send_resolved": False,
        "http_config": {"http_headers": {"X-Webhook-Secret": {"files": [HEADER_FILE]}}}}],
        "pagerduty_configs": copy.deepcopy(integrations)}
    route = {"receiver": RECEIVER, "matchers": ['page="devin"', 'namespace="otterworks-odl"']}
    if "group_wait" in oncall_routes[0]:
        route["group_wait"] = oncall_routes[0]["group_wait"]
    existing_receivers = [r for r in updated["receivers"] if r["name"] == RECEIVER]
    existing_routes = [r for r in routes if r.get("receiver") == RECEIVER]
    if existing_receivers or existing_routes:
        if len(existing_receivers) == 1:
            webhooks = existing_receivers[0].get("webhook_configs", [])
            if len(webhooks) == 1 and webhooks[0].get("send_resolved") is True:
                webhooks[0]["send_resolved"] = False
        if (existing_receivers != [receiver] or existing_routes != [route]
                or routes.index(existing_routes[0]) + 1 != routes.index(oncall_routes[0])):
            raise ValueError("Existing ODL receiver or route differs; refusing to overwrite it")
        return updated
    routes.insert(routes.index(oncall_routes[0]), route)
    updated["receivers"].append(receiver)
    return updated


def structure(config):
    return {"route": config["route"], "receivers": [
        {"name": r["name"], **{k: [
            {"fields": sorted(i), **({"url": "<redacted>"} if "url" in i else {}),
             **({"send_resolved": i["send_resolved"]} if "send_resolved" in i else {}),
             **({"url_file": i["url_file"]} if "url_file" in i else {}),
             **({"http_headers": {name: {key: value if key == "files" else "<redacted>"
                                         for key, value in header.items()}
                                  for name, header in i["http_config"]["http_headers"].items()}}
                if "http_headers" in i.get("http_config", {}) else {}),
             **({"routing_key_file": i["routing_key_file"]} if "routing_key_file" in i else {})}
            for i in v] for k, v in r.items() if k.endswith("_configs")}}
        for r in config["receivers"]]}


def main():
    root = Path(__file__).resolve().parents[2]
    spec = kubectl("get", "alertmanager", "prometheus-alertmanager")["spec"]
    source = spec.get("configSecret") or "alertmanager-prometheus-alertmanager"
    original = kubectl("get", "secret", source)
    config = yaml.safe_load(base64.b64decode(original["data"]["alertmanager.yaml"]))
    updated = updated_config(config)
    ensure_webhook_secret()
    before = yaml.safe_dump(structure(config), sort_keys=False).splitlines(keepends=True)
    after = yaml.safe_dump(structure(updated), sort_keys=False).splitlines(keepends=True)
    print("".join(difflib.unified_diff(before, after, fromfile="before (redacted)",
                                     tofile="after (redacted)", n=0)), flush=True)
    data = {k: base64.b64decode(v).decode() for k, v in original["data"].items()}
    data["alertmanager.yaml"] = yaml.safe_dump(updated, sort_keys=False)
    target = secret(CONFIG_SECRET, data)
    existing = subprocess.check_output(["kubectl", "-n", "monitoring", "get", "secret", CONFIG_SECRET,
                                        "--ignore-not-found", "-o", "json"], text=True)
    if existing.strip():
        target["metadata"]["resourceVersion"] = json.loads(existing)["metadata"]["resourceVersion"]
    write_secret(target, create=not existing.strip())
    # A mounted Secret list is replaced by Helm, not merged. Preserve unrelated mounts.
    overlay = yaml.safe_load((root / "observability/alertmanager/k8s/odl-routing-values.yaml").read_text())
    mounts = overlay["alertmanager"]["alertmanagerSpec"]["secrets"]
    overlay["alertmanager"]["alertmanagerSpec"]["secrets"] = sorted(set(mounts + spec.get("secrets", [])))
    subprocess.run(["helm", "upgrade", "prometheus", "prometheus-community/kube-prometheus-stack",
                    "--namespace", "monitoring", "--version", "92.6.0", "--reuse-values",
                    "--labels", f"run_token={RUN_TOKEN}", "-f", "-", "--wait", "--timeout", "10m"],
                   input=yaml.safe_dump(overlay), text=True, check=True)


if __name__ == "__main__":
    main()
