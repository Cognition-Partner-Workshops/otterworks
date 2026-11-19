#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCOPE=all
if [ "$#" -ne 0 ]; then
  [ "$#" -eq 2 ] && [ "$1" = --only ] && [ "$2" = confluence ] || {
    echo "Usage: $0 [--only confluence]" >&2; exit 1;
  }
  SCOPE=confluence
fi
if [ "$SCOPE" = all ]; then
  kubectl apply -f "${ROOT}/infrastructure/k8s/odl-mocks/namespace.yaml"
else
  kubectl get namespace odl-mocks >/dev/null
fi
python3 - "$SCOPE" <<'PY'
import base64
import json
import secrets
import subprocess
import sys

names = ("confluence-mock-basic-auth",) if sys.argv[1] == "confluence" else (
    "jira-mock-basic-auth", "pagerduty-mock-basic-auth", "confluence-mock-basic-auth")
for name in names:
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
              "metadata": {"name": name, "namespace": "odl-mocks",
                           "labels": {"run_token": "odl-1795112287"}},
              "data": {k: base64.b64encode(v.encode()).decode() for k, v in values.items()}}
    subprocess.run(["kubectl", "create", "-f", "-"], input=json.dumps(secret),
                   text=True, check=True, stdout=subprocess.DEVNULL)
    print("created", name)
PY
if [ "$SCOPE" = confluence ]; then
  kubectl apply -k "${ROOT}/infrastructure/k8s/odl-mocks" -l app=confluence
else
  kubectl apply -k "${ROOT}/infrastructure/k8s/odl-mocks"
  kubectl -n odl-mocks rollout status deployment/jira --timeout=300s
  kubectl -n odl-mocks rollout status deployment/pagerduty --timeout=300s
fi
kubectl -n odl-mocks rollout status deployment/confluence --timeout=300s
