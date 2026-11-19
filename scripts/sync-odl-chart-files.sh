#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/services/operational-data-layer/deploy/files"
rc=0
for pair in observability/prometheus/odl_rules.yml:odl_rules.yml observability/grafana/dashboards/odl-overview.json:odl-overview.json; do
  src="$ROOT/${pair%%:*}"
  dst="$DEST/${pair##*:}"
  if [ "${1:-}" = --check ]; then
    if ! cmp -s "$src" "$dst"; then
      echo "drift: ${pair%%:*} (run scripts/sync-odl-chart-files.sh)" >&2
      rc=1
    fi
  else
    mkdir -p "$DEST"
    cp "$src" "$dst"
    echo "synced ${pair%%:*}"
  fi
done
exit "$rc"
