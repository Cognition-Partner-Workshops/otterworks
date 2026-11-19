#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ID="${1:?Usage: deploy-odl-ui.sh odl}"
[[ "$ID" = odl ]] || { echo "UI overrides are restricted to tenant odl" >&2; exit 2; }
NS="otterworks-${ID}"
RENDERER="${ROOT}/scripts/odl/helm-labels.py"

helm upgrade api-gateway "${ROOT}/infrastructure/helm/api-gateway" -n "$NS" \
  --reuse-values -f "${ROOT}/scripts/odl/t-odl-gateway.values.yaml" \
  --post-renderer "$RENDERER" --labels run_token=odl-1795112287 --wait --timeout 4m
helm upgrade --install admin-dashboard "${ROOT}/infrastructure/helm/admin-dashboard" -n "$NS" \
  -f "${ROOT}/scripts/odl/t-odl-admin.values.yaml" \
  --post-renderer "$RENDERER" --labels run_token=odl-1795112287 --wait --timeout 4m
