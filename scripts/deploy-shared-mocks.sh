#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
kubectl apply -f "${ROOT}/infrastructure/k8s/shared-mocks/namespace.yaml"
python3 - <<'PY'
import base64
import json
import secrets
import subprocess

for name in ("jira-mock-basic-auth", "pagerduty-mock-basic-auth", "confluence-mock-basic-auth"):
    result = subprocess.run(["kubectl", "-n", "odl-mocks", "get", "secret", name,
                             "--ignore-not-found", "-o", "json"],
                            check=True, capture_output=True, text=True)
    if result.stdout.strip():
        continue
    password = secrets.token_urlsafe(32)
    hashed = subprocess.run(["openssl", "passwd", "-apr1", "-stdin"],
                            input=password + "\n", text=True, capture_output=True,
                            check=True).stdout.strip()
    values = {"username": "odl", "password": password, "auth": "odl:" + hashed + "\n"}
    secret = {"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
              "metadata": {"name": name, "namespace": "odl-mocks"},
              "data": {k: base64.b64encode(v.encode()).decode() for k, v in values.items()}}
    subprocess.run(["kubectl", "create", "-f", "-"], input=json.dumps(secret),
                   text=True, check=True, stdout=subprocess.DEVNULL)
    print("created", name)
PY
kubectl apply -k "${ROOT}/infrastructure/k8s/shared-mocks"
kubectl -n odl-mocks rollout status deployment/jira --timeout=300s
kubectl -n odl-mocks rollout status deployment/pagerduty --timeout=300s
kubectl -n odl-mocks rollout status deployment/confluence --timeout=300s
