#!/usr/bin/env bash
# Offline tests for scripts/sandbox-messaging.sh with stubbed terraform, aws and python.
# Run: bash scripts/tests/test_sandbox_messaging_sh.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/sandbox-messaging.sh"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
LOG="${WORK}/calls.log"
pass=0; fail=0

cat > "${WORK}/terraform" <<'STUB'
#!/usr/bin/env bash
echo "terraform cwd=${PWD} data=${TF_DATA_DIR:-} $*" >> "$STUB_LOG"
case "$1" in
  show) echo '{"resource_changes":[]}' ;;
  output) echo '{"run_token":{"value":"rs-20261006-ab"}}' ;;
esac
exit 0
STUB
cat > "${WORK}/aws" <<'STUB'
#!/usr/bin/env bash
echo "aws $*" >> "$STUB_LOG"
case "$1" in
  resourcegroupstaggingapi) echo "${STUB_TAGGED:-}" ;;
  *) echo "" ;;
esac
STUB
cat > "${WORK}/python" <<'STUB'
#!/usr/bin/env bash
echo "python $*" >> "$STUB_LOG"
case " $* " in *" plan-guard "*) exit "${STUB_GUARD_RC:-0}" ;; esac
exit 0
STUB
chmod +x "${WORK}/terraform" "${WORK}/aws" "${WORK}/python"

run() {  # run <env...> -- <args>
  : > "$LOG"
  env STUB_LOG="$LOG" TERRAFORM="${WORK}/terraform" AWS="${WORK}/aws" PYTHON="${WORK}/python" \
    STATE_DIR="${WORK}/state" PURGE_SETTLE_SECONDS=0 VERIFY_WAIT_SECONDS=0 "$@" > "${WORK}/out" 2>&1
}
check() {  # check <name> <condition...>
  local name="$1"; shift
  if "$@"; then pass=$((pass + 1)); echo "ok   - ${name}"; else fail=$((fail + 1)); echo "FAIL - ${name}"; sed 's/^/       /' "${WORK}/out" "$LOG"; fi
}
logged() { grep -qF -- "$1" "$LOG"; }
not_logged() { ! grep -qF -- "$1" "$LOG"; }

run "$SCRIPT" plan; rc=$?
check "plan without RUN is refused" test "$rc" = 2
check "plan without RUN calls nothing" test ! -s "$LOG"

run RUN=lp-20261006-ab "$SCRIPT" plan; rc=$?
check "legacy-portal tokens are refused" test "$rc" = 2

run RUN=rs-20261006-ab STATE_DIR="${REPO_ROOT}/.sbx-state" "$SCRIPT" plan; rc=$?
rm -rf "${REPO_ROOT}/.sbx-state"
check "state inside the repository is refused" test "$rc" = 2

run RUN=rs-20261006-ab "$SCRIPT" destroy; rc=$?
check "destroy without CONFIRM is refused" test "$rc" = 2
check "destroy without CONFIRM calls nothing" test ! -s "$LOG"

run RUN=rs-20261006-ab EXPIRES=2026-10-07T20:00:00Z "$SCRIPT" up; rc=$?
check "up succeeds" test "$rc" = 0
check "up inits with per-token local state outside the repo" logged "-backend-config=path=${WORK}/state/rs-20261006-ab/after.tfstate"
check "up keeps terraform data outside the repo" logged "data=${WORK}/state/rs-20261006-ab/.terraform-after"
check "up runs in the sandbox root" logged "cwd=${REPO_ROOT}/infrastructure/terraform/reliability-sandbox data="
check "up passes run token and expiry" logged "-var run_token=rs-20261006-ab -var expires=2026-10-07T20:00:00Z"
check "up guards the plan" logged "plan-guard --plan-json ${WORK}/state/rs-20261006-ab/after.tfplan.json --run-token rs-20261006-ab"
check "up applies exactly the saved plan" logged "apply -input=false ${WORK}/state/rs-20261006-ab/after.tfplan"
check "up never auto-approves" not_logged "-auto-approve"

run RUN=rs-20261006-ab STUB_GUARD_RC=1 "$SCRIPT" up; rc=$?
check "a plan outside the token stops up" test "$rc" = 2
check "a rejected plan is never applied" not_logged "terraform cwd=${REPO_ROOT}/infrastructure/terraform/reliability-sandbox data=${WORK}/state/rs-20261006-ab/.terraform-after apply"

run RUN=rs-20261006-ab PHASE=before "$SCRIPT" plan; rc=$?
check "PHASE=before plans the before twin" logged "cwd=${REPO_ROOT}/infrastructure/terraform/reliability-sandbox/before data="
check "PHASE=before has its own state file" logged "path=${WORK}/state/rs-20261006-ab/before.tfstate"

run RUN=rs-20261006-ab PHASE=before "$SCRIPT" replay; rc=$?
check "replay refuses the before stack" test "$rc" = 2

run RUN=rs-20261006-ab "$SCRIPT" verify-clean; rc=$?
check "verify-clean passes when nothing is left" test "$rc" = 0
check "verify-clean asks the tagging API for the token" logged "Key=run_token,Values=rs-20261006-ab"

run RUN=rs-20261006-ab STUB_TAGGED="arn:aws:sqs:us-east-1:111111111111:rs-20261006-ab-analytics-events-dev" "$SCRIPT" verify-clean; rc=$?
check "verify-clean fails while a tagged resource remains" test "$rc" = 1

mkdir -p "${WORK}/state/rs-20261006-ab" && echo '{}' > "${WORK}/state/rs-20261006-ab/after.tfstate"
run RUN=rs-20261006-ab CONFIRM=rs-20261006-ab "$SCRIPT" destroy; rc=$?
check "destroy with CONFIRM succeeds" test "$rc" = 0
check "destroy plans with -destroy and allows deletes in the guard" logged "--allow-delete"
check "destroy skips a phase with no state" grep -q "no before state" "${WORK}/out"

echo "${pass} passed, ${fail} failed"
[ "$fail" = 0 ]
