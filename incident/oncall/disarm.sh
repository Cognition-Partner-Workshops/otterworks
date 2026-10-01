#!/usr/bin/env bash
# shellcheck disable=SC2016 # jq filters are single-quoted on purpose
# Disarm one or both on-call tenants: stop the k6 Job and, when the worker is
# on, ship the reverse config deploy (folderDigest.enabled=false, oncall_run
# label removed). Safe to run on a tenant that is not armed.
#
# Usage: incident/oncall/disarm.sh [oncall-before|oncall-after ...]
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_bins kubectl helm jq curl
ensure_kubeconfig

mapfile -t targets < <(tenants_or_both "$@")
for tenant in "${targets[@]}"; do
  ns="$(tenant_ns "${tenant}")"
  if ! kubectl get ns "${ns}" >/dev/null 2>&1; then
    warn "${ns} does not exist; nothing to disarm"
    continue
  fi
  log "Disarming ${tenant}"
  kubectl -n "${ns}" delete job "${K6_JOB}" --ignore-not-found --wait=true >/dev/null
  kubectl -n "${ns}" delete configmap "${K6_CONFIGMAP}" --ignore-not-found >/dev/null
  revision=""
  if [ "$(digest_enabled "${tenant}")" = true ]; then
    digest_deploy "${tenant}" false ""
    revision="$(helm_revision "${tenant}")"
    grafana_annotate "${tenant}" "document-service rev ${revision}: folder digest worker disabled"
    log "document-service rev ${revision}: folder digest worker disabled"
  else
    log "folder digest worker already off in ${ns}"
  fi
  if [ -f "$(state_file "${tenant}")" ]; then
    state_update "${tenant}" '.disarmed_at = $at | .steps.disarm = {at: $at, revision: $rev}' \
      --arg at "$(now_iso)" --arg rev "${revision}"
  fi
done
