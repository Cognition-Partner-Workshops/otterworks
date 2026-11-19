#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
kubectl apply -f "${ROOT}/infrastructure/k8s/odl-mocks/namespace.yaml"
python3 - <<'PY'
import base64
import json
import os
import secrets
import subprocess


def exists(name):
    result = subprocess.run(["kubectl", "-n", "odl-mocks", "get", "secret", name,
                             "--ignore-not-found", "-o", "json"],
                            check=True, capture_output=True, text=True)
    return bool(result.stdout.strip())


def create_secret(name, values):
    secret = {"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
              "metadata": {"name": name, "namespace": "odl-mocks",
                           "labels": {"run_token": "odl-1795112287"}},
              "data": {k: base64.b64encode(v.encode()).decode() for k, v in values.items()}}
    result = subprocess.run(["kubectl", "create", "-f", "-"], input=json.dumps(secret),
                            text=True, capture_output=True)
    if result.returncode:
        raise SystemExit(f"Could not create {name} (kubectl exit {result.returncode})")
    print("created", name)


relay = "jira-devin-webhook"
if not exists(relay):
    values = {key: os.environ.get(key) for key in ("DEVIN_JIRA_WEBHOOK_URL", "DEVIN_JIRA_WEBHOOK_SECRET")}
    if not all(values.values()):
        raise SystemExit(f"Set DEVIN_JIRA_WEBHOOK_URL and DEVIN_JIRA_WEBHOOK_SECRET to create {relay}")
    create_secret(relay, values)

for name in ("jira-mock-basic-auth", "pagerduty-mock-basic-auth"):
    if exists(name):
        continue
    password = secrets.token_urlsafe(32)
    hashed = subprocess.run(["openssl", "passwd", "-apr1", "-stdin"],
                            input=password + "\n", text=True, capture_output=True,
                            check=True).stdout.strip()
    create_secret(name, {"username": "odl", "password": password, "auth": "odl:" + hashed + "\n"})
PY
kubectl apply -k "${ROOT}/infrastructure/k8s/odl-mocks"
kubectl -n odl-mocks rollout status deployment/jira-devin-relay --timeout=300s
kubectl -n odl-mocks rollout status deployment/jira --timeout=300s
kubectl -n odl-mocks rollout status deployment/pagerduty --timeout=300s
