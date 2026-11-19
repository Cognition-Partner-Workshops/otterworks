#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# OtterWorks - switch one tenant between the default single-replica layout and
# the high-availability profile (HPA min 2 / max 6, PDB, zone + node spread).
#
#   ./scripts/scale-for-load.sh <ATTENDEE_ID> up   [service ...]
#   ./scripts/scale-for-load.sh <ATTENDEE_ID> down [service ...]
#
# Defaults to the core request path. Check capacity first: every service at
# min 2 roughly doubles the tenant's CPU requests (see docs/RELIABILITY-READINESS.md).
# ------------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=SCRIPTDIR/lib/tenant-common.sh
source "${SCRIPT_DIR}/lib/tenant-common.sh"

ATTENDEE_ID="${1:-}"; DIRECTION="${2:-}"
[ -n "${ATTENDEE_ID}" ] && [ -n "${DIRECTION}" ] || { err "Usage: $0 <ATTENDEE_ID> <up|down> [service ...]"; exit 1; }
shift 2
SERVICES=("$@")
[ ${#SERVICES[@]} -gt 0 ] || SERVICES=(api-gateway auth-service document-service file-service web-app)
require_bins kubectl helm
NS="$(tenant_namespace "${ATTENDEE_ID}")"
PROFILE="${REPO_ROOT}/infrastructure/helm/profiles/high-availability.yaml"

for svc in "${SERVICES[@]}"; do
  helm status "${svc}" -n "${NS}" >/dev/null 2>&1 || { warn "${svc} not deployed in ${NS}; skipping"; continue; }
  case "${DIRECTION}" in
    up)
      log "${NS}/${svc}: high-availability profile"
      helm upgrade "${svc}" "${REPO_ROOT}/infrastructure/helm/${svc}" -n "${NS}" --reuse-values -f "${PROFILE}" --wait --timeout 10m ;;
    down)
      log "${NS}/${svc}: back to single replica"
      helm upgrade "${svc}" "${REPO_ROOT}/infrastructure/helm/${svc}" -n "${NS}" --reuse-values \
        --set autoscaling.enabled=false --set replicaCount=1 --wait --timeout 10m ;;
    *) err "direction must be up or down"; exit 1 ;;
  esac
done
kubectl get hpa,pdb -n "${NS}"
