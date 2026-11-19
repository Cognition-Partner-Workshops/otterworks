#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ID="${1:?Usage: deploy-odl-runtime.sh odl}"
[[ "$ID" = odl ]] || { echo "Runtime update is restricted to tenant odl" >&2; exit 2; }

helm upgrade --install operational-data-layer "${ROOT}/services/operational-data-layer/deploy" \
  -n "otterworks-${ID}" --post-renderer "${ROOT}/scripts/odl/helm-labels.py" \
  --labels run_token=odl-1795112287 --wait --timeout 4m
"${ROOT}/scripts/odl/deploy-odl-ui.sh" "$ID"
