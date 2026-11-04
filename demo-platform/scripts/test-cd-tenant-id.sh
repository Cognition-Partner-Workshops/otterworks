#!/usr/bin/env bash
# Offline tests for cd_branch_tenant_id (scripts/lib/tenant-common.sh), the
# workflow-side mirror of the dashboard's cdTenantIdForBranch().
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=scripts/lib/tenant-common.sh
source "${ROOT}/scripts/lib/tenant-common.sh"

fails=0
ok()   { local got; got="$(TENANT_PREFIX="${3:-}" PERPETUAL_TENANT_IDS="main,cloud-worker" cd_branch_tenant_id "$1" 2>/dev/null)" && [ "${got}" = "$2" ] || { echo "FAIL: $1 -> '${got:-<refused>}', want $2"; fails=$((fails + 1)); }; }
nope() { if TENANT_PREFIX="${2:-}" PERPETUAL_TENANT_IDS="main,cloud-worker" cd_branch_tenant_id "$1" >/dev/null 2>&1; then echo "FAIL: $1 accepted"; fails=$((fails + 1)); fi; }

ok workshop-alice alice
ok demo-retail-2 retail-2
ok demo-main gtm-main gtm
nope workshop-main
nope demo-main
nope workshop-cloud-worker
nope workshop-Main
nope workshop-a_b
nope workshop-a--b
nope workshop--main
nope workshop-main-
nope workshop-
nope workshop/main
nope main
nope "workshop-$(printf 'a%.0s' $(seq 41))"
# Unset PERPETUAL_TENANT_IDS still protects main.
if (unset PERPETUAL_TENANT_IDS; cd_branch_tenant_id workshop-main >/dev/null 2>&1); then echo "FAIL: default perpetual"; fails=$((fails + 1)); fi

[ "${fails}" -eq 0 ] && echo "cd_branch_tenant_id: all passed" || exit 1
