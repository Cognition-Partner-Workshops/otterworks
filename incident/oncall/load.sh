#!/usr/bin/env bash
# (Re)start the oncall-k6 Job on an armed tenant, so the load run starts now.
# The after proof uses it: arm with --no-load, apply migration 005, then start
# the load, so the k6 summary only covers a run that had the index.
#
# Usage: incident/oncall/load.sh <oncall-before|oncall-after>
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

tenant="${1:-}"
require_tenant "${tenant}"
require_bins kubectl jq envsubst
ensure_kubeconfig
ns="$(tenant_ns "${tenant}")"
require_ns "${ns}"
wake_tenant "${tenant}" "${PG_DEPLOY}" document-service api-gateway
[ "$(digest_enabled "${tenant}")" = true ] ||
  die "the folder digest worker is off in ${ns}; run make oncall-arm TENANT=${tenant} first"
log "k6 load (${LOAD_VUS} VUs, ${LOAD_MINUTES} min) against https://$(api_host "${tenant}")"
start_load "${tenant}"
log "Load running. Gate: make oncall-verify TENANT=${tenant} EXPECT=<before|after>"
