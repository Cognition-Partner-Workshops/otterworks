#!/usr/bin/env bash
# Offline regression tests for scripts/lp-ec2.sh. aws, terraform, curl, mvn and
# sleep are stubbed on PATH; nothing reaches AWS.
#   bash scripts/tests/lp-ec2_test.sh
# Conditions are passed to check() in single quotes so they expand after each run.
# shellcheck disable=SC2016,SC2034
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lp-ec2.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
ROOT="$T/root"; BIN="$T/bin"
mkdir -p "$ROOT/scripts" "$ROOT/infrastructure/terraform/legacy-portal-ec2" "$ROOT/services/legacy-portal" "$BIN"
cp "$SRC" "$ROOT/scripts/lp-ec2.sh"
export RUN=lp-ec2-20261006-t1 STUB_LOG="$T/calls.log" VERIFY_WAIT_SECONDS=0 HEALTH_WAIT_SECONDS=60

# Each STUB_<lookup> is absent (default), present, denied or unreachable.
cat >"$BIN/aws" <<'STUB'
#!/usr/bin/env bash
echo "aws $*" >>"$STUB_LOG"
answer() { # $1 state, $2 not-found error text
  case "$1" in
    present) echo '{}' ;;
    absent) echo "An error occurred ($2) when calling the operation: not found" >&2; exit 254 ;;
    denied) echo "An error occurred (AccessDenied) when calling the operation: not authorized" >&2; exit 254 ;;
    unreachable) echo "Could not connect to the endpoint URL: \"https://example.invalid/\"" >&2; exit 255 ;;
  esac
}
case "$1 $2" in
  "sts get-caller-identity") case "$*" in *Account*) echo 123456789012 ;; *) echo arn:aws:iam::123456789012:user/tester ;; esac ;;
  "ec2 describe-regions") echo "us-east-1 us-west-2" ;;
  "resourcegroupstaggingapi get-resources")
    [ "${STUB_tagging:-0}" = error ] && { echo "An error occurred (ThrottlingException)" >&2; exit 254; }
    case "$*" in *"--output json"*) echo '{"ResourceTagMappingList":[]}' ;; *) echo "${STUB_tagging:-0}" ;; esac ;;
  "iam get-role") answer "${STUB_role:-absent}" NoSuchEntity ;;
  "iam get-instance-profile") answer "${STUB_profile:-absent}" NoSuchEntity ;;
  "elbv2 describe-load-balancers") answer "${STUB_lb:-absent}" LoadBalancerNotFound ;;
  "elbv2 describe-target-groups") answer "${STUB_tg:-absent}" TargetGroupNotFound ;;
  "s3api head-bucket")
    case "${STUB_bucket:-absent}" in
      absent) echo "An error occurred (404) when calling the HeadBucket operation: Not Found" >&2; exit 254 ;;
      denied) echo "An error occurred (403) when calling the HeadBucket operation: Forbidden" >&2; exit 254 ;;
      *) answer "$STUB_bucket" NoSuchBucket ;;
    esac ;;
  "logs describe-log-groups")
    [ "${STUB_logs:-0}" = error ] && { echo "An error occurred (ThrottlingException)" >&2; exit 254; }
    echo "${STUB_logs:-0}" ;;
  "elbv2 describe-target-health")
    n=$(( $(cat "$STUB_LOG.health" 2>/dev/null || echo 0) + 1 )); echo "$n" >"$STUB_LOG.health"
    if [ "$n" -le "${STUB_health_failures:-0}" ]; then echo "An error occurred (Throttling) when calling the DescribeTargetHealth operation: Rate exceeded" >&2; exit 254; fi
    echo healthy ;;
  "ec2 describe-instances") echo instance ;;
  *) echo "unexpected aws $*" >&2; exit 99 ;;
esac
STUB

# Mimics filemd5(): plan, apply and destroy fail when the jar_path file is missing.
cat >"$BIN/terraform" <<'STUB'
#!/usr/bin/env bash
echo "terraform $*" >>"$STUB_LOG"
dir="${1#-chdir=}"; shift
jar="../../../services/legacy-portal/target/legacy-portal.jar"
for a in "$@"; do case "$a" in jar_path=*) jar="${a#jar_path=}" ;; esac; done
case "$1" in
  init) exit 0 ;;
  output)
    if [ "${2:-}" = -json ]; then
      echo '{"base_url":{"value":"http://alb.example/"},"instance_id":{"value":"i-0abc"},"target_group_arn":{"value":"arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/x/1"}}'
    else echo "base_url = http://alb.example/"; fi ;;
  plan|apply|destroy)
    [ "$1" = apply ] && exit 0
    [ -f "$dir/$jar" ] || { echo "Error: Error in function call: filemd5: no file exists at \"$dir/$jar\"" >&2; exit 1; }
    echo "$1 ok" ;;
esac
STUB

cat >"$BIN/curl" <<'STUB'
#!/usr/bin/env bash
echo "curl $*" >>"$STUB_LOG"
echo "  GET /health 200 in 0.01s"
STUB

cat >"$BIN/mvn" <<'STUB'
#!/usr/bin/env bash
mkdir -p target && echo jar > target/legacy-portal.jar
STUB

printf '#!/bin/sh\nexit 0\n' >"$BIN/sleep"
chmod +x "$BIN"/*
export PATH="$BIN:$PATH"

pass=0; fail=0
run() { : >"$STUB_LOG"; rm -f "$STUB_LOG.health"; OUT="$(env "${@:2}" bash "$ROOT/scripts/lp-ec2.sh" "$1" 2>&1)"; RC=$?; }
check() { # name, condition
  if eval "$2"; then pass=$((pass + 1)); echo "ok   $1"
  else fail=$((fail + 1)); echo "FAIL $1"; printf '     | %s\n' "${OUT//$'\n'/$'\n'     | }"; fi
}

run verify-clean
check "verify-clean: everything absent is CLEAN" '[ $RC = 0 ] && grep -q "^CLEAN" <<<"$OUT"'

run verify-clean STUB_role=present
check "verify-clean: a remaining role is NOT CLEAN" '[ $RC = 1 ] && grep -q "still present: ${RUN}-instance" <<<"$OUT" && grep -q "^NOT CLEAN" <<<"$OUT"'

run verify-clean STUB_role=denied
check "verify-clean: AccessDenied on GetRole is not proof of absence" '[ $RC = 1 ] && grep -q "^NOT CLEAN" <<<"$OUT" && grep -q "unknown: ${RUN}-instance (.*AccessDenied" <<<"$OUT"'

run verify-clean STUB_profile=unreachable STUB_lb=unreachable STUB_tg=unreachable
check "verify-clean: unreachable endpoints are not proof of absence" '[ $RC = 1 ] && grep -q "^NOT CLEAN" <<<"$OUT" && ! grep -q "absent: ${RUN}$" <<<"$OUT"'

run verify-clean STUB_bucket=denied
check "verify-clean: HeadBucket 403 is not proof of absence" '[ $RC = 1 ] && grep -q "^NOT CLEAN" <<<"$OUT" && ! grep -q "absent: ${RUN}-artifacts" <<<"$OUT"'

run verify-clean STUB_logs=error
check "verify-clean: a failed log-group lookup reports NOT CLEAN" '[ $RC = 1 ] && grep -q "^NOT CLEAN" <<<"$OUT"'

run verify-clean STUB_tagging=error
check "verify-clean: a failed tagging API call reports NOT CLEAN" '[ $RC = 1 ] && grep -q "^NOT CLEAN" <<<"$OUT"'

rm -f "$ROOT/services/legacy-portal/target/legacy-portal.jar"
run down
check "down: destroys without a built jar" '[ $RC = 0 ] && grep -q "destroy ok" <<<"$OUT"'
check "down: does not create the jar in the build output" '[ ! -e "$ROOT/services/legacy-portal/target/legacy-portal.jar" ]'

run up STUB_health_failures=2
check "up: a transient DescribeTargetHealth error does not abort the health wait" '[ $RC = 0 ] && grep -q "target health: healthy" <<<"$OUT"'

run status
check "status: the ALB health probe has a bounded deadline" '[ $RC = 0 ] && grep -q -- "--max-time" "$STUB_LOG"'

echo "${pass} passed, ${fail} failed"
[ "$fail" = 0 ]
