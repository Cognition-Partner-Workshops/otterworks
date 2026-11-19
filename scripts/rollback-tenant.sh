#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/tenant-common.sh
source "${SCRIPT_DIR}/lib/tenant-common.sh"

usage() { err "Usage: $0 <ID> [service|all] [--to-revision N] [--dry-run]"; exit 1; }
ID=""
SERVICE="all"
SERVICE_SET=false
REVISION=""
DRY_RUN=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --to-revision) [ "$#" -ge 2 ] || usage; REVISION="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -*) usage ;;
    *)
      if [ -z "${ID}" ]; then ID="$1"
      elif [ "${SERVICE_SET}" = false ]; then SERVICE="$1"; SERVICE_SET=true
      else usage; fi
      shift ;;
  esac
done
if [ -z "${ID}" ] || [ -z "$(sanitize_id "${ID}")" ]; then usage; fi
if [ -n "${REVISION}" ] && ! [[ "${REVISION}" =~ ^[1-9][0-9]*$ ]]; then usage; fi
require_bins helm kubectl jq
NS="$(tenant_namespace "${ID}")"
RELEASES=()
if [ "${SERVICE}" = all ]; then
  releases="$(helm list -n "${NS}" --all -o json)"
  for service in "${ALL_SERVICES[@]}"; do
    if jq -e --arg name "${service}" 'any(.[]; .name == $name)' <<< "${releases}" >/dev/null; then
      RELEASES+=("${service}")
    fi
  done
else
  case " ${ALL_SERVICES[*]} " in
    *" ${SERVICE} "*) RELEASES+=("${SERVICE}") ;;
    *) err "Unknown app service: ${SERVICE}"; exit 1 ;;
  esac
fi
[ "${#RELEASES[@]}" -gt 0 ] || { err "No app releases in ${NS}"; exit 1; }
FAILED=()
for service in "${RELEASES[@]}"; do
  log "History for ${NS}/${service}"
  helm history "${service}" -n "${NS}"
  target="${REVISION}"
  if [ -z "${target}" ]; then
    history="$(helm history "${service}" -n "${NS}" -o json)"
    target="$(jq -r 'sort_by(.revision | tonumber) | if length > 1 then .[-2].revision else empty end' <<< "${history}")"
    if [ -z "${target}" ]; then
      warn "${service}: no previous revision; skipping"
      FAILED+=("${service}")
      continue
    fi
  fi
  args=(rollback "${service}" "${target}" -n "${NS}" --wait --timeout "${ROLLBACK_TIMEOUT:-4m}")
  if [ "${DRY_RUN}" = true ]; then
    printf 'DRY RUN: helm'; printf ' %q' "${args[@]}"; printf '\n'
    continue
  fi
  if ! helm "${args[@]}"; then FAILED+=("${service}"); continue; fi
  deployments="$(kubectl -n "${NS}" get deployments -l "app.kubernetes.io/instance=${service}" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')" || { FAILED+=("${service}"); continue; }
  [ -n "${deployments}" ] || { warn "${service}: no deployment found"; FAILED+=("${service}"); continue; }
  while IFS= read -r deployment; do
    if ! kubectl -n "${NS}" rollout status "deployment/${deployment}" --timeout="${VERIFY_TIMEOUT:-120s}"; then
      FAILED+=("${service}")
    fi
  done <<< "${deployments}"
done
if [ "${#FAILED[@]}" -gt 0 ]; then err "Rollback issues: ${FAILED[*]}"; exit 1; fi
log "Rollback complete (${NS}, dry-run=${DRY_RUN})"
