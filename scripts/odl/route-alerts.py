#!/usr/bin/env python3
"""Preserve live routing while externalizing the Devin URL and adding ODL paging."""

import base64
import copy
import difflib
import json
import subprocess
from pathlib import Path

import yaml

RUN_TOKEN = "odl-1795112287"
CONFIG_SECRET = "alertmanager-odl-config"
WEBHOOK_SECRET = "alertmanager-devin-webhook"
PAGERDUTY_SECRET = "alertmanager-odl-pagerduty"
URL_FILE = f"/etc/alertmanager/secrets/{WEBHOOK_SECRET}/url"
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
    subprocess.run(["kubectl", "-n", "monitoring", "create" if create else "replace", "-f", "-"],
                   input=json.dumps(obj), text=True, check=True, stdout=subprocess.DEVNULL)


def ensure_secret(name, values):
    current = subprocess.check_output(["kubectl", "-n", "monitoring", "get", "secret", name,
                                       "--ignore-not-found", "-o", "json"], text=True)
    if not current.strip():
        write_secret(secret(name, values), create=True)
        return
    obj = json.loads(current)
    for key, value in values.items():
        if base64.b64decode(obj["data"][key]).decode() != value:
            raise ValueError(f"Existing {name} differs; refusing to overwrite credentials")


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
    receivers = [r for r in updated["receivers"] if r["name"] == "devin-oncall"]
    if len(receivers) != 1 or len(receivers[0].get("webhook_configs", [])) != 1:
        raise ValueError("Expected exactly one devin-oncall webhook")
    receiver = receivers[0]
    webhook = receiver["webhook_configs"][0]
    url = webhook.pop("url", None)
    if not url and webhook.get("url_file") != URL_FILE:
        raise ValueError("Unexpected Devin webhook configuration")
    webhook["url_file"] = URL_FILE
    integrations = receiver.setdefault("pagerduty_configs", [])
    if not any(p.get("url") == EVENTS_URL for p in integrations):
        integrations.append({"url": EVENTS_URL, "routing_key_file": KEY_FILE,
                             "send_resolved": True,
                             "description": '{{ .CommonLabels.alertname }}: {{ .CommonAnnotations.summary }}',
                             "severity": "error"})
    return updated, url


def structure(config):
    return {"route": config["route"], "receivers": [
        {"name": r["name"], **{k: [
            {"fields": sorted(i), **({"url": "<redacted>"} if "url" in i else {}),
             **({"url_file": i["url_file"]} if "url_file" in i else {}),
             **({"routing_key_file": i["routing_key_file"]} if "routing_key_file" in i else {})}
            for i in v] for k, v in r.items() if k.endswith("_configs")}}
        for r in config["receivers"]]}


def main():
    root = Path(__file__).resolve().parents[2]
    spec = kubectl("get", "alertmanager", "prometheus-alertmanager")["spec"]
    source = spec.get("configSecret") or "alertmanager-prometheus-alertmanager"
    original = kubectl("get", "secret", source)
    config = yaml.safe_load(base64.b64decode(original["data"]["alertmanager.yaml"]))
    updated, url = updated_config(config)
    if url:
        ensure_secret(WEBHOOK_SECRET, {"url": url})
    else:
        kubectl("get", "secret", WEBHOOK_SECRET)
    ensure_secret(PAGERDUTY_SECRET, {"routing_key": pagerduty_routing_key()})
    before = yaml.safe_dump(structure(config), sort_keys=False).splitlines(keepends=True)
    after = yaml.safe_dump(structure(updated), sort_keys=False).splitlines(keepends=True)
    print("".join(difflib.unified_diff(before, after, fromfile="before (redacted)",
                                     tofile="after (redacted)")), flush=True)
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
