#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Unit tests for the lifetime a finished deploy leaves on its tenant.
#
# A deploy job is enqueued with a TTL. If the tenant is pinned while that job
# runs, the job must not hand it a finite expiry when it finishes: the namespace
# reaper deletes on the namespace annotation alone, so a pinned tenant would
# quietly die three days later.
#
# aws / kubectl / deploy-tenant.sh are stubbed; this runs anywhere.
# ------------------------------------------------------------------------------
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok   - $1"; }
nope() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else nope "$1 (expected '$3', got '$2')"; fi; }

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/../lib/control-common.sh"

# ---- stubs -------------------------------------------------------------------
REPO_DIR="$(mktemp -d)"
trap 'rm -rf "${REPO_DIR}"' EXIT
mkdir -p "${REPO_DIR}/scripts"
printf '#!/bin/sh\nexit 0\n' > "${REPO_DIR}/scripts/deploy-tenant.sh"
chmod +x "${REPO_DIR}/scripts/deploy-tenant.sh"

# shellcheck disable=SC2034
DB_PASSWORD=x TIER=A TTL=72h HOST_SUFFIX=demo.example TENANT_ID=skin
ITEM='{}'
SET_EXP=""
ANNOTATED=""
log() { :; }; err() { :; }; die() { echo "die: $*" >&2; return 1; }
sanitize_id() { printf '%s' "$1"; }
tenant_namespace() { printf 'otterworks-%s' "$1"; }
tenant_db_name() { printf 'otterworks_%s' "$1"; }
ctl_update_status() { :; }
ctl_audit() { :; }
ctl_set_active() { SET_EXP="$6"; }
aws() { [ "${2:-}" = "get-item" ] && printf '%s' "${ITEM}"; }
kubectl() { ANNOTATED="$*"; }

eval "$(sed -n '/^expiry_epoch()/,/^}/p; /^run_deploy()/,/^}/p' "${SCRIPT_DIR}/entrypoint.sh")"

NOW="$(date -u +%s)"
FAR=$(( NOW + 10 * 365 * 86400 ))
item() {
  jq -nc --arg e "$1" --arg pin "$2" --arg p "$3" \
    '{Item: ({PK:{S:"TENANT#skin"}, SK:{S:"META"}, expires_at:{N:$e}}
      + (if $pin == "" then {} else {pinned:{BOOL:($pin == "true")}} end)
      + (if $p == "" then {} else {persistent:{BOOL:($p == "true")}} end))}'
}
run() { ITEM="$1"; SET_EXP=""; ANNOTATED=""; run_deploy >/dev/null 2>&1; }
finite() { [ "${SET_EXP}" -ge $(( NOW + 72 * 3600 )) ] && [ "${SET_EXP}" -le $(( NOW + 72 * 3600 + 60 )) ] && echo yes || echo no; }

echo "deploy lifetime"

run "$(item "${FAR}" true "")"
check "pinned mid-deploy: record keeps its expiry" "${SET_EXP}" "${FAR}"
case "${ANNOTATED}" in
  *"demo/expires-at-epoch=${FAR}"*) ok "pinned mid-deploy: namespace annotation follows" ;;
  *) nope "pinned mid-deploy: namespace annotation follows (got '${ANNOTATED}')" ;;
esac

run "$(item "${FAR}" "" true)"
check "perpetual: record keeps its expiry" "${SET_EXP}" "${FAR}"

run "$(item "${FAR}" false false)"
check "ordinary tenant: gets the job's TTL" "$(finite)" "yes"
check "ordinary tenant: annotation left to deploy-tenant.sh" "${ANNOTATED}" ""

run '{}'
check "no record: gets the job's TTL" "$(finite)" "yes"
check "no record: annotation left to deploy-tenant.sh" "${ANNOTATED}" ""

echo
echo "${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ]
