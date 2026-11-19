#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
"$ROOT/scripts/sync-odl-chart-files.sh" --check
helm upgrade --install odl-observability "$ROOT/services/operational-data-layer/deploy" \
  -n monitoring --set mongodb.enabled=false --set sync.enabled=false --set observability.enabled=true \
  --labels run_token=odl-1795112287 --wait --timeout 3m
