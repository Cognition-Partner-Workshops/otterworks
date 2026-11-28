#!/usr/bin/env bash
set -euo pipefail
DEMO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ROOT=$(git -C "$DEMO" rev-parse --show-toplevel)
CHART="$ROOT/platform/standards/helm/app"
NAMESPACE=devops-fleet
WORKLOADS=(api-gateway auth-service collab-service document-service file-service search-service)

render_or_install() {
  local mode=$1 workload=$2
  shift 2
  helm "$mode" "$workload" "$CHART" --namespace "$NAMESPACE" \
    -f "$DEMO/values/common.yaml" -f "$DEMO/values/$workload.yaml" "$@"
}
