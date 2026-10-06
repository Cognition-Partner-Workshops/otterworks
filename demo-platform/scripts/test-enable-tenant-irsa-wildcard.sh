#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Tests for enable-tenant-irsa-wildcard.sh.
#
# deploy-tenant.sh stops adding per-tenant trust statements only once a role
# carries the wildcard, so a role this script silently skipped keeps growing
# toward the trust-policy size quota until tenant deploys fail. A role that
# could not be read must therefore fail the run, not read as "not found".
#
# The aws CLI is stubbed on PATH; nothing here touches a real account.
# ------------------------------------------------------------------------------
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${SCRIPT_DIR}/enable-tenant-irsa-wildcard.sh"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok   - $1"; }
nope() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else nope "$1 (expected '$3', got '$2')"; fi; }

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
mkdir -p "${WORK}/bin"

cat > "${WORK}/bin/aws" <<'STUB'
#!/usr/bin/env bash
oidc="oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE"
case "$*" in
  *"eks describe-cluster"*) echo "https://${oidc}" ;;
  *"iam get-role"*)
    case "${GET_ROLE_MODE}" in
      throttle) echo "An error occurred (Throttling) when calling the GetRole operation: Rate exceeded" >&2; exit 255 ;;
      missing)  echo "An error occurred (NoSuchEntity) when calling the GetRole operation: The role cannot be found." >&2; exit 254 ;;
      wildcard)
        svc="$(echo "$*" | sed -n 's/.*--role-name otterworks-\(.*\)-dev.*/\1/p')"
        printf '{"Statement":[{"Effect":"Allow","Principal":{"Federated":"arn"},"Condition":{"StringLike":{"%s:sub":"system:serviceaccount:otterworks-*:%s"}}}]}\n' "${oidc}" "${svc}" ;;
      *) printf '{"Statement":[{"Effect":"Allow","Principal":{"Federated":"arn"},"Condition":{"StringEquals":{"%s:sub":"system:serviceaccount:otterworks:x"}}}]}\n' "${oidc}" ;;
    esac ;;
  *"iam update-assume-role-policy"*) echo update >> "${STATE}/updates.log" ;;
esac
exit 0
STUB
chmod +x "${WORK}/bin/aws"

run() {
  local state="${WORK}/state.$RANDOM$RANDOM"
  mkdir -p "${state}"
  OUT="$(env PATH="${WORK}/bin:${PATH}" STATE="${state}" GET_ROLE_MODE="$1" ENV=dev bash "${TARGET}" 2>&1)"
  RC=$?
  UPDATES=0
  if [ -e "${state}/updates.log" ]; then UPDATES="$(wc -l < "${state}/updates.log" | tr -d ' ')"; fi
}

echo "enable-tenant-irsa-wildcard"

run throttle
check "fails when a role cannot be read" "${RC}" "1"
case "${OUT}" in *"not found"*) r=misreported ;; *) r=reported ;; esac
check "  and does not report it as not found" "${r}" "reported"

run missing
check "skips roles that genuinely do not exist" "${RC}" "0"
check "  without updating anything" "${UPDATES}" "0"

run plain
check "adds the wildcard to every role" "${UPDATES}" "10"
check "  and succeeds" "${RC}" "0"

run wildcard
check "is idempotent once the wildcard is present" "${UPDATES}" "0"

echo
echo "${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ]
