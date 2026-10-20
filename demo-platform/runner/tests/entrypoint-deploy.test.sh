#!/usr/bin/env bash
# Regression tests for runner/entrypoint.sh OP=deploy status bookkeeping.
# Runs the real entrypoint against a scratch REPO_DIR with a stubbed
# deploy-tenant.sh and a fake `aws` that records calls instead of touching AWS.
#   bash demo-platform/runner/tests/entrypoint-deploy.test.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../../.." && pwd)"
ENTRYPOINT="${ENTRYPOINT:-${ROOT}/demo-platform/runner/entrypoint.sh}"
fails=0

setup() {
  WORK="$(mktemp -d)"
  mkdir -p "${WORK}/repo/scripts/lib" "${WORK}/repo/demo-platform/lib" "${WORK}/bin"
  cp "${ROOT}/scripts/lib/tenant-common.sh" "${WORK}/repo/scripts/lib/"
  cp "${ROOT}/demo-platform/lib/control-common.sh" "${WORK}/repo/demo-platform/lib/"
  cat > "${WORK}/bin/aws" <<'AWS'
#!/usr/bin/env bash
# One line per call (the JSON args are multi-line) so tests can grep it.
printf '%s\n' "$(printf '%s ' "$@" | tr -s '\n ' ' ')" >> "${AWS_CALLS}"
AWS
  chmod +x "${WORK}/bin/aws"
  export AWS_CALLS="${WORK}/aws-calls.log"; : > "${AWS_CALLS}"
}

stub_deploy() {
  printf '#!/usr/bin/env bash\n%s\n' "$1" > "${WORK}/repo/scripts/deploy-tenant.sh"
  chmod +x "${WORK}/repo/scripts/deploy-tenant.sh"
}

run_entrypoint() {
  env -i PATH="${WORK}/bin:${PATH}" HOME="${WORK}" AWS_CALLS="${AWS_CALLS}" \
    OP=deploy TENANT_ID=t1 DB_PASSWORD=unit-test REPO_DIR="${WORK}/repo" \
    KUBERNETES_SERVICE_HOST=unit-test "$@" bash "${ENTRYPOINT}" >"${WORK}/out.log" 2>&1
}

check() {
  local name="$1"; shift
  if "$@"; then echo "ok   - ${name}"; else echo "FAIL - ${name}"; fails=$((fails + 1)); sed 's/^/     | /' "${WORK}/out.log" "${AWS_CALLS}"; fi
}

status_written() { grep -q "update-item.*\"S\": *\"$1\"" "${AWS_CALLS}"; }
audit_written()  { grep -q "put-item.*$1" "${AWS_CALLS}"; }

# 1. A deploy that outlives RUNNER_OP_TIMEOUT_SECONDS is recorded as error.
setup; stub_deploy 'exec sleep 30'
started=$(date +%s); rc=0; run_entrypoint RUNNER_OP_TIMEOUT_SECONDS=1 || rc=$?
elapsed=$(( $(date +%s) - started ))
check "timed-out deploy exits non-zero" test "${rc}" -ne 0
check "timed-out deploy returns promptly (${elapsed}s)" test "${elapsed}" -lt 15
check "timed-out deploy sets status=error" status_written error
check "timed-out deploy audits deploy_fail with timeout" audit_written 'deploy_fail.*timed out after 1s'
check "timed-out deploy never marks active" bash -c "! grep -q '\"active\"' '${AWS_CALLS}'"
rm -rf "${WORK}"

# 2. A successful deploy still marks the tenant active.
setup; stub_deploy 'exit 0'
rc=0; run_entrypoint RUNNER_OP_TIMEOUT_SECONDS=60 || rc=$?
check "successful deploy exits zero" test "${rc}" -eq 0
check "successful deploy sets status=active" status_written active
check "successful deploy audits deploy_ok" audit_written deploy_ok
rm -rf "${WORK}"

# 3. A failing deploy keeps the original non-timeout audit detail.
setup; stub_deploy 'exit 3'
rc=0; run_entrypoint RUNNER_OP_TIMEOUT_SECONDS=60 || rc=$?
check "failed deploy exits non-zero" test "${rc}" -ne 0
check "failed deploy sets status=error" status_written error
check "failed deploy audits non-zero return" audit_written 'deploy_fail.*returned non-zero'
rm -rf "${WORK}"

# 4. Without RUNNER_OP_TIMEOUT_SECONDS (older dashboards) the deploy is unbounded.
setup; stub_deploy 'sleep 2; exit 0'
rc=0; run_entrypoint || rc=$?
check "unset timeout runs deploy to completion" status_written active
rm -rf "${WORK}"

[ "${fails}" -eq 0 ] && echo "all entrypoint deploy tests passed" || { echo "${fails} failure(s)"; exit 1; }
