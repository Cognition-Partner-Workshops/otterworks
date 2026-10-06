#!/usr/bin/env bash
# Harness for the legacy-portal EC2 "before" state: Terraform root, jar build,
# replay and teardown per run token.
#   scripts/lp-ec2.sh up|status|replay|down|verify-clean
# Inputs come from the environment: RUN (lp-ec2-<yyyymmdd>-<two chars>), CTX, STAGE, EXPIRES_DAYS.
# Every command writes a transcript to .demo/legacy-portal/<token>/<command>-<UTC time>.log with the
# AWS account number replaced by <account>.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_ROOT="${ROOT}/infrastructure/terraform/legacy-portal-ec2"
PARITY="${ROOT}/services/legacy-portal/parity"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
export AWS_PAGER="" TF_IN_AUTOMATION=1
CMD="${1:-}"; shift || true

die() { echo "lp-ec2: $*" >&2; exit 2; }
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

need_run() {
  [ -n "${RUN:-}" ] || die "RUN is required, e.g. make lp-ec2-${CMD} RUN=lp-ec2-$(date -u +%Y%m%d)-b1"
  [[ "$RUN" =~ ^lp-ec2-[0-9]{8}-[a-z0-9]{2}$ ]] || die "RUN must look like lp-ec2-20261006-b1, got ${RUN}"
}

start_transcript() {
  local dir="${ROOT}/.demo/legacy-portal/${1}"
  mkdir -p "$dir"
  TRANSCRIPT="${dir}/${CMD}-$(date -u +%Y%m%dT%H%M%SZ).log"
  local account
  account="$(aws sts get-caller-identity --query Account --output text)"
  exec > >(sed -u -E "s/${account}/<account>/g" | tee "$TRANSCRIPT") 2>&1
  echo "# lp-ec2-${CMD} run=${1} started $(now)"
  echo "# caller $(aws sts get-caller-identity --query Arn --output text | sed -E 's#:user/.*#:user/<caller>#')"
  trap 'rc=$?; echo "# lp-ec2-${CMD} finished $(now) exit=${rc}"; echo "# transcript ${TRANSCRIPT#"${ROOT}"/}"' EXIT
}

tf() { TF_DATA_DIR="${ROOT}/.demo/legacy-portal/${RUN}/.terraform" terraform -chdir="$TF_ROOT" "$@"; }

tf_init() {
  tf init -input=false -reconfigure -no-color \
    -backend-config="key=otterworks/legacy-portal-ec2/${RUN}/terraform.tfstate" >/dev/null
  echo "terraform init: state otterworks/legacy-portal-ec2/${RUN}/terraform.tfstate"
}

tf_vars() {
  local expires_file="${ROOT}/.demo/legacy-portal/${RUN}/expires"
  if [ ! -s "$expires_file" ]; then
    date -u -d "+${EXPIRES_DAYS:-3} days" +%Y-%m-%d > "$expires_file"
  fi
  TF_VARS=(-var "run_token=${RUN}" -var "expires=$(cat "$expires_file")")
}

elapsed() { awk -v s="$1" -v e="$(date +%s)" 'BEGIN { printf "%d s (%.1f min)", e - s, (e - s) / 60 }'; }

build_jar() {
  if ! command -v mvn >/dev/null && [ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]; then
    # shellcheck source=/dev/null
    source "$HOME/.sdkman/bin/sdkman-init.sh" >/dev/null
  fi
  local mvn="./mvnw"
  command -v mvn >/dev/null && mvn="mvn"
  # Maven Central rate-limits this egress IP (HTTP 429); the Google Cloud
  # Storage mirror of central carries the same artifacts.
  local settings="${ROOT}/.demo/legacy-portal/maven-settings.xml"
  mkdir -p "$(dirname "$settings")"
  cat >"$settings" <<'XML'
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0">
  <mirrors>
    <mirror>
      <id>google-maven-central</id>
      <name>Google Cloud Storage mirror of Maven Central</name>
      <url>https://maven-central.storage-download.googleapis.com/maven2/</url>
      <mirrorOf>central</mirrorOf>
    </mirror>
  </mirrors>
</settings>
XML
  (cd "${ROOT}/services/legacy-portal" && "$mvn" -s "$settings" -q -DskipTests package)
  ls -l "${ROOT}/services/legacy-portal/target/legacy-portal.jar"
}

load_outputs() {
  local json
  json="$(tf output -json)"
  [ "$(jq 'length' <<<"$json")" -gt 0 ] || die "no Terraform outputs for ${RUN}; run make lp-ec2-up RUN=${RUN} first"
  BASE_URL="$(jq -r .base_url.value <<<"$json")"
  INSTANCE_ID="$(jq -r .instance_id.value <<<"$json")"
  TG_ARN="$(jq -r .target_group_arn.value <<<"$json")"
}

wait_healthy() {
  local deadline=$(( $(date +%s) + ${HEALTH_WAIT_SECONDS:-900} )) state
  echo "waiting for the ALB health check on ${TG_ARN##*:targetgroup/} (up to $(( ${HEALTH_WAIT_SECONDS:-900} / 60 )) min)"
  while :; do
    # A throttled or failed call is retried on the next poll instead of aborting after the apply.
    state="$(aws elbv2 describe-target-health --target-group-arn "$TG_ARN" \
      --query 'TargetHealthDescriptions[0].TargetHealth.State' --output text 2>&1)" || state="lookup failed: ${state##*$'\n'}"
    echo "$(now) target health: ${state}"
    [ "$state" = healthy ] && return 0
    [ "$(date +%s)" -lt "$deadline" ] || die "target still ${state} after the wait window"
    sleep 15
  done
}

cmd_up() {
  need_run; start_transcript "$RUN"
  local t0; t0="$(date +%s)"
  build_jar
  tf_init; tf_vars
  tf plan -input=false -no-color "${TF_VARS[@]}" -out="${ROOT}/.demo/legacy-portal/${RUN}/up.tfplan"
  tf apply -input=false -no-color -auto-approve "${ROOT}/.demo/legacy-portal/${RUN}/up.tfplan"
  echo
  tf output -no-color
  load_outputs
  echo
  wait_healthy
  echo
  echo "lp-ec2-up wall clock: $(elapsed "$t0")"
}

cmd_status() {
  local scope="${RUN:-all-runs}"
  [ -z "${RUN:-}" ] || need_run
  start_transcript "$scope"
  echo "resources tagged demo=legacy-portal-ec2 in ${AWS_REGION}, by run_token:"
  aws resourcegroupstaggingapi get-resources --tag-filters Key=demo,Values=legacy-portal-ec2 --output json \
    | jq -r '.ResourceTagMappingList[] | [(.Tags[] | select(.Key=="run_token") | .Value), (.ResourceARN | split(":")[2])] | @tsv' \
    | sort | uniq -c | awk '{ printf "  %-18s %-16s %s\n", $2, $3, $1 }'
  [ -n "${RUN:-}" ] || { echo "set RUN=<token> for one run's outputs, instance and health"; return 0; }
  tf_init >/dev/null
  if [ "$(tf output -json | jq length)" -eq 0 ]; then echo "no Terraform state with outputs for ${RUN}"; return 0; fi
  load_outputs
  echo; echo "outputs:"; tf output -no-color
  echo; echo "instance:"
  aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --output table \
    --query 'Reservations[0].Instances[0].{id:InstanceId,state:State.Name,type:InstanceType,az:Placement.AvailabilityZone,launched:LaunchTime}'
  echo "target health:"
  aws elbv2 describe-target-health --target-group-arn "$TG_ARN" --output table \
    --query 'TargetHealthDescriptions[0].{target:Target.Id,port:Target.Port,state:TargetHealth.State,reason:TargetHealth.Reason}'
  echo "health of the ALB:"
  curl -s --connect-timeout 5 --max-time 20 -o /dev/null -w '  GET /health %{http_code} in %{time_total}s\n' "${BASE_URL%/}/health" || true
}

cmd_replay() {
  need_run; start_transcript "$RUN"
  local ctx="${CTX:-all}" stage="${STAGE:-full}" out rc=0
  case "$stage" in first|full) ;; *) die "STAGE must be first or full" ;; esac
  tf_init >/dev/null; load_outputs
  out="${ROOT}/.demo/legacy-portal/${RUN}/replay-${stage}-${ctx}-$(date -u +%Y%m%dT%H%M%SZ)"
  echo "target ${BASE_URL}  context ${ctx}  stage ${stage}"
  (cd "$PARITY" && sha256sum -c SHA256SUMS)
  python3 "${PARITY}/replay.py" --base "$BASE_URL" --context "$ctx" --stage "$stage" --out "$out" || rc=$?
  echo "replay exit ${rc} (0 all identical, 1 divergences found, 3 corpus checksum mismatch)"
  return "$rc"
}

cmd_down() {
  need_run; start_transcript "$RUN"
  local t0; t0="$(date +%s)"
  tf_init; tf_vars
  # filemd5() on the jar is evaluated during destroy too; without a built jar
  # (fresh checkout, mvn clean) point it at an empty stand-in under .demo.
  if [ ! -f "${TF_ROOT}/../../../services/legacy-portal/target/legacy-portal.jar" ]; then
    : >"${ROOT}/.demo/legacy-portal/${RUN}/destroy-placeholder.jar"
    TF_VARS+=(-var "jar_path=../../../.demo/legacy-portal/${RUN}/destroy-placeholder.jar")
    echo "no built jar; destroying with an empty stand-in for the jar's checksum"
  fi
  tf destroy -input=false -no-color -auto-approve "${TF_VARS[@]}"
  echo
  echo "lp-ec2-down wall clock: $(elapsed "$t0")"
}

cmd_verify_clean() {
  need_run; start_transcript "$RUN"
  local deadline=$(( $(date +%s) + ${VERIFY_WAIT_SECONDS:-600} )) left regions problems
  regions="$(aws ec2 describe-regions --query 'Regions[].RegionName' --output text)"
  while :; do
    left=0; problems=()
    for r in $regions; do
      for key in run_token RunToken; do
        n="$(aws resourcegroupstaggingapi get-resources --region "$r" --tag-filters "Key=${key},Values=${RUN}" \
          --query 'length(ResourceTagMappingList)' --output text 2>/dev/null || echo error)"
        [ "$n" = 0 ] || { left=1; problems+=("tagging API ${r} ${key}=${RUN}: ${n}"); }
      done
    done
    [ "$left" = 0 ] || [ "$(date +%s)" -ge "$deadline" ] && break
    echo "$(now) still listed: ${problems[*]}; the tagging API can trail deletes, retrying in 30 s"
    sleep 30
  done
  echo "tagging API, all $(wc -w <<<"$regions") regions, run_token=${RUN} and RunToken=${RUN}: $([ "$left" = 0 ] && echo 0 resources || echo "${problems[*]}")"
  if [ "$left" = 1 ]; then
    aws resourcegroupstaggingapi get-resources --tag-filters "Key=run_token,Values=${RUN}" --query 'ResourceTagMappingList[].ResourceARN' --output text || true
  fi
  # IAM is global and the tagging API does not list every resource type, so check the run's named objects directly.
  # Only the service's not-found error proves absence; AccessDenied, throttling, a 403 from
  # HeadBucket or an unreachable endpoint leave the object unknown, which is not clean.
  check_gone() {
    local notfound="$1" err; shift
    if err="$("$@" 2>&1 >/dev/null)"; then echo "  still present: ${*: -1}"; left=1
    elif grep -qE "$notfound" <<<"$err"; then echo "  absent: ${*: -1}"
    else echo "  unknown: ${*: -1} ($(tr -s '\n' ' ' <<<"$err"))"; left=1; fi
  }
  echo "direct lookups:"
  check_gone '\(NoSuchEntity\)' aws iam get-role --role-name "${RUN}-instance"
  check_gone '\(NoSuchEntity\)' aws iam get-instance-profile --instance-profile-name "${RUN}-instance"
  check_gone '\(LoadBalancerNotFound\)' aws elbv2 describe-load-balancers --names "$RUN"
  check_gone '\(TargetGroupNotFound\)' aws elbv2 describe-target-groups --names "${RUN}-app"
  check_gone '\((404|NoSuchBucket)\)' aws s3api head-bucket --bucket "${RUN}-artifacts"
  n="$(aws logs describe-log-groups --log-group-name-prefix "/otterworks/legacy-portal-ec2/${RUN}" --query 'length(logGroups)' --output text 2>/dev/null || echo error)"
  echo "  log groups matching /otterworks/legacy-portal-ec2/${RUN}: ${n}"; [ "$n" = 0 ] || left=1
  if [ "$left" = 0 ]; then echo "CLEAN: nothing tagged or named ${RUN} remains"; else echo "NOT CLEAN"; return 1; fi
}

case "$CMD" in
  up) cmd_up ;;
  status) cmd_status ;;
  replay) cmd_replay ;;
  down) cmd_down ;;
  verify-clean) cmd_verify_clean ;;
  *) die "usage: lp-ec2.sh up|status|replay|down|verify-clean (RUN, CTX, STAGE from the environment)" ;;
esac
