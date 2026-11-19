#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# OtterWorks - shared-cluster reliability add-ons (idempotent).
#
#   1. metrics-server (EKS managed add-on): resource metrics for HPAs and
#      `kubectl top`. Without it every HorizontalPodAutoscaler stays <unknown>.
#   2. ingress-nginx ServiceMonitor: edge SLIs for every tenant and frontend.
#   3. otterworks-reliability PrometheusRule: SLO, capacity and health alerts.
#
# Usage: ./scripts/install-cluster-addons.sh [--cluster otterworks-dev] [--dry-run]
# ------------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLUSTER="${CLUSTER_NAME:-otterworks-dev}"
DRY_RUN=false
while [ $# -gt 0 ]; do
  case "$1" in
    --cluster) CLUSTER="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

run() { if [ "${DRY_RUN}" = true ]; then echo "+ $*"; else "$@"; fi; }

if aws eks describe-addon --cluster-name "${CLUSTER}" --addon-name metrics-server >/dev/null 2>&1; then
  echo "metrics-server add-on already installed"
else
  K8S_VERSION="$(aws eks describe-cluster --name "${CLUSTER}" --query cluster.version --output text)"
  VERSION="$(aws eks describe-addon-versions --addon-name metrics-server --kubernetes-version "${K8S_VERSION}" \
    --query 'addons[0].addonVersions[0].addonVersion' --output text)"
  echo "installing metrics-server ${VERSION}"
  run aws eks create-addon --cluster-name "${CLUSTER}" --addon-name metrics-server --addon-version "${VERSION}"
  [ "${DRY_RUN}" = true ] || aws eks wait addon-active --cluster-name "${CLUSTER}" --addon-name metrics-server
fi

APPLY_ARGS=()
[ "${DRY_RUN}" = true ] && APPLY_ARGS=(--dry-run=server)
kubectl apply "${APPLY_ARGS[@]}" -f "${REPO_ROOT}/infrastructure/k8s/monitoring/"
echo "done"
