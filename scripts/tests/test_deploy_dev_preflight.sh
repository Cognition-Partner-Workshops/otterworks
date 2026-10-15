#!/usr/bin/env bash
# Offline tests for scripts/deploy-dev.sh argument and preflight handling.
# Every external tool is a stub; the run stops at the first AWS call.
# Run: bash scripts/tests/test_deploy_dev_preflight.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/deploy-dev.sh"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
LOG="${WORK}/calls.log"
pass=0; fail=0

for tool in aws docker helm kubectl terraform jq; do
  cat > "${WORK}/${tool}" <<STUB
#!/usr/bin/env bash
echo "${tool} \$*" >> "\$STUB_LOG"
[ "${tool}" = aws ] && exit 1
exit 0
STUB
  chmod +x "${WORK}/${tool}"
done

run() {
  : > "$LOG"
  env -u DB_PASSWORD PATH="${WORK}:${PATH}" STUB_LOG="$LOG" AWS_ACCOUNT_ID=111111111111 "$@" > "${WORK}/out" 2>&1
}
check() {
  local name="$1"; shift
  if "$@"; then pass=$((pass + 1)); echo "ok   - ${name}"; else fail=$((fail + 1)); echo "FAIL - ${name}"; sed 's/^/       /' "${WORK}/out" "$LOG"; fi
}
no_terraform() { ! grep -q '^terraform' "$LOG"; }

run "$SCRIPT" --skip-terrafrom; rc=$?
check "a mistyped flag is rejected" test "$rc" = 2
check "a mistyped flag runs no terraform" no_terraform
check "a mistyped flag names the option" grep -q "unknown option: --skip-terrafrom" "${WORK}/out"

run "$SCRIPT"; rc=$?
check "missing DB_PASSWORD fails" test "$rc" = 1
check "missing DB_PASSWORD fails before the platform apply" no_terraform
check "missing DB_PASSWORD explains itself" grep -q "DB_PASSWORD must be set" "${WORK}/out"

run "$SCRIPT" --skip-platform; rc=$?
check "missing DB_PASSWORD with --skip-platform still fails before terraform" test "$rc" = 1
check "--skip-platform without DB_PASSWORD runs no terraform" no_terraform

run "$SCRIPT" --skip-terraform; rc=$?
check "--skip-terraform does not need DB_PASSWORD (stops at stub aws)" grep -q '^aws eks update-kubeconfig' "$LOG"
check "--skip-terraform runs no terraform" no_terraform

run "$SCRIPT" --help; rc=$?
check "--help exits 0" test "$rc" = 0
check "--help prints usage" grep -q "Usage:" "${WORK}/out"

echo "${pass} passed, ${fail} failed"
[ "$fail" = 0 ]
