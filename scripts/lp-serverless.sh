#!/usr/bin/env bash
# Harness for the legacy-portal-serverless demo: Terraform root, replay, reset and teardown per run token.
#   scripts/lp-serverless.sh up|replay|status|reset|down|verify-clean
# Inputs come from the environment: RUN (lp-<yyyymmdd>-<two letters>), CTX, STAGE, EXPIRES_DAYS.
# Every command writes a transcript to .demo/legacy-portal/<token>/<command>-<UTC time>.log with the
# AWS account number replaced by <account>.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_ROOT="${ROOT}/infrastructure/terraform/legacy-portal-serverless"
PARITY="${ROOT}/services/legacy-portal/parity"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
export AWS_PAGER="" TF_IN_AUTOMATION=1
CMD="${1:-}"; shift || true

die() { echo "lp-serverless: $*" >&2; exit 2; }
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

need_run() {
  [ -n "${RUN:-}" ] || die "RUN is required, e.g. make lp-${CMD} RUN=lp-$(date -u +%Y%m%d)-rh"
  [[ "$RUN" =~ ^lp-[0-9]{8}-[a-z]{2}$ ]] || die "RUN must look like lp-20261005-rh, got ${RUN}"
}

start_transcript() {
  local dir="${ROOT}/.demo/legacy-portal/${1}"
  mkdir -p "$dir"
  TRANSCRIPT="${dir}/${CMD}-$(date -u +%Y%m%dT%H%M%SZ).log"
  local account
  account="$(aws sts get-caller-identity --query Account --output text)"
  exec > >(sed -u -E "s/${account}/<account>/g" | tee "$TRANSCRIPT") 2>&1
  echo "# lp-${CMD} run=${1} started $(now)"
  echo "# caller $(aws sts get-caller-identity --query Arn --output text | sed -E 's#:user/.*#:user/<caller>#')"
  trap 'rc=$?; echo "# lp-${CMD} finished $(now) exit=${rc}"; echo "# transcript ${TRANSCRIPT#"${ROOT}"/}"' EXIT
}

tf() { TF_DATA_DIR="${ROOT}/.demo/legacy-portal/${RUN}/.terraform" terraform -chdir="$TF_ROOT" "$@"; }

tf_init() {
  tf init -input=false -reconfigure -no-color \
    -backend-config="key=otterworks/legacy-portal-serverless/${RUN}/terraform.tfstate" >/dev/null
  echo "terraform init: state otterworks/legacy-portal-serverless/${RUN}/terraform.tfstate"
}

tf_vars() {
  local expires_file="${ROOT}/.demo/legacy-portal/${RUN}/expires"
  if [ ! -s "$expires_file" ]; then
    date -u -d "+${EXPIRES_DAYS:-2} days" +%Y-%m-%d > "$expires_file"
  fi
  TF_VARS=(-var "run_token=${RUN}" -var "expires=$(cat "$expires_file")")
}

elapsed() { awk -v s="$1" -v e="$(date +%s)" 'BEGIN { printf "%d s (%.1f min)", e - s, (e - s) / 60 }'; }

data_api() {
  local sql="$1" out attempt
  for attempt in $(seq 1 30); do
    if out="$(aws rds-data execute-statement --resource-arn "$CLUSTER_ARN" --secret-arn "$SECRET_ARN" \
        --database "$DB_NAME" --sql "$sql" --output json 2>&1)"; then
      printf '%s\n' "$out"; return 0
    fi
    case "$out" in
      *DatabaseResumingException*|*"is not available"*|*"Communications link failure"*)
        echo "waiting for the cluster to resume (attempt ${attempt})" >&2; sleep 10 ;;
      *) echo "$out" >&2; return 1 ;;
    esac
  done
  return 1
}

load_outputs() {
  local json
  json="$(tf output -json)"
  [ "$(jq 'length' <<<"$json")" -gt 0 ] || die "no Terraform outputs for ${RUN}; run make lp-up RUN=${RUN} first"
  API_URL="$(jq -r .api_url.value <<<"$json")"
  CLUSTER_ARN="$(jq -r .aurora_cluster_arn.value <<<"$json")"
  SECRET_ARN="$(jq -r .db_secret_arn.value <<<"$json")"
  DB_NAME="$(jq -r .db_name.value <<<"$json")"
  OUTPUTS_JSON="$json"
}

cmd_up() {
  need_run; start_transcript "$RUN"
  local t0; t0="$(date +%s)"
  tf_init; tf_vars
  tf plan -input=false -no-color "${TF_VARS[@]}" -out="${ROOT}/.demo/legacy-portal/${RUN}/up.tfplan"
  tf apply -input=false -no-color -auto-approve "${ROOT}/.demo/legacy-portal/${RUN}/up.tfplan"
  echo
  tf output -no-color
  echo
  echo "lp-up wall clock: $(elapsed "$t0")"
}

cmd_replay() {
  need_run; start_transcript "$RUN"
  local ctx="${CTX:-all}" stage="${STAGE:-first}" out rc=0
  case "$stage" in first|full) ;; *) die "STAGE must be first or full" ;; esac
  tf_init >/dev/null; load_outputs
  out="${ROOT}/.demo/legacy-portal/${RUN}/replay-${stage}-${ctx}-$(date -u +%Y%m%dT%H%M%SZ)"
  echo "target ${API_URL}  context ${ctx}  stage ${stage}"
  (cd "$PARITY" && sha256sum -c SHA256SUMS)
  python3 "${PARITY}/replay.py" --base "$API_URL" --context "$ctx" --stage "$stage" --out "$out" || rc=$?
  echo "replay exit ${rc} (0 all identical, 1 divergences found, 3 corpus checksum mismatch)"
  # A first-stage replay that stops at a divergence is the expected pause, not a failure of the harness.
  if [ "$stage" = first ] && [ "$rc" = 1 ]; then return 0; fi
  return "$rc"
}

cmd_status() {
  local scope="${RUN:-all-runs}"
  [ -z "${RUN:-}" ] || need_run
  start_transcript "$scope"
  echo "resources tagged demo=legacy-portal-serverless in ${AWS_REGION}, by run_token:"
  aws resourcegroupstaggingapi get-resources --tag-filters Key=demo,Values=legacy-portal-serverless --output json \
    | jq -r '.ResourceTagMappingList[] | [(.Tags[] | select(.Key=="run_token") | .Value), (.ResourceARN | split(":")[2])] | @tsv' \
    | sort | uniq -c | awk '{ printf "  %-18s %-16s %s\n", $2, $3, $1 }'
  [ -n "${RUN:-}" ] || { echo "set RUN=<token> for one run's outputs, cluster and functions"; return 0; }
  tf_init >/dev/null
  if [ "$(tf output -json | jq length)" -eq 0 ]; then echo "no Terraform state with outputs for ${RUN}"; return 0; fi
  load_outputs
  echo; echo "outputs:"; tf output -no-color
  echo; echo "aurora:"
  aws rds describe-db-clusters --db-cluster-identifier "$RUN" --output table \
    --query 'DBClusters[0].{status:Status,engine:EngineVersion,minACU:ServerlessV2ScalingConfiguration.MinCapacity,maxACU:ServerlessV2ScalingConfiguration.MaxCapacity,pause:ServerlessV2ScalingConfiguration.SecondsUntilAutoPause,dataApi:HttpEndpointEnabled}'
  echo "functions:"
  for fn in $(jq -r '.lambda_names.value[]' <<<"$OUTPUTS_JSON"); do
    aws lambda get-function-configuration --function-name "$fn" --output text \
      --query '[FunctionName,Runtime,MemorySize,State,LastModified]'
  done
  echo "health of the API (the placeholder answers 501):"
  curl -s -o /dev/null -w '  GET /health %{http_code} in %{time_total}s\n' "${API_URL%/}/health" || true
}

cmd_reset() {
  need_run; start_transcript "$RUN"
  local ctx="${CTX:-all}" tables
  case "$ctx" in
    all) tables="announcements.announcement, user_preferences.user_preference, feedback.feedback" ;;
    announcements) tables="announcements.announcement" ;;
    preferences|user_preferences) tables="user_preferences.user_preference" ;;
    feedback) tables="feedback.feedback" ;;
    common) echo "the common cases keep no data; nothing to reset"; return 0 ;;
    *) die "CTX must be announcements, preferences, feedback, common or all" ;;
  esac
  tf_init >/dev/null; load_outputs
  data_api "TRUNCATE ${tables} RESTART IDENTITY" >/dev/null
  echo "truncated ${tables} and restarted the id sequences (the seeded state is empty tables, ids from 1)"
  data_api "SELECT (SELECT count(*) FROM announcements.announcement) AS announcements, (SELECT count(*) FROM user_preferences.user_preference) AS user_preferences, (SELECT count(*) FROM feedback.feedback) AS feedback" \
    | jq -r '"rows after reset: announcements=\(.records[0][0].longValue) user_preferences=\(.records[0][1].longValue) feedback=\(.records[0][2].longValue)"'
}

cmd_down() {
  need_run; start_transcript "$RUN"
  local t0; t0="$(date +%s)"
  tf_init; tf_vars
  tf destroy -input=false -no-color -auto-approve "${TF_VARS[@]}"
  echo
  echo "lp-down wall clock: $(elapsed "$t0")"
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
    aws resourcegroupstaggingapi get-resources --tag-filters "Key=run_token,Values=${RUN}" --query 'ResourceTagMappingList[].ResourceARN' --output text
  fi
  # IAM is global and the tagging API does not list every IAM type, so check the run's IAM objects by name.
  check_gone() { if "$@" >/dev/null 2>&1; then echo "  still present: ${*: -1}"; left=1; else echo "  absent: ${*: -1}"; fi; }
  local account; account="$(aws sts get-caller-identity --query Account --output text)"
  echo "direct lookups:"
  check_gone aws iam get-role --role-name "${RUN}-lambda"
  check_gone aws iam get-policy --policy-arn "arn:aws:iam::${account}:policy/${RUN}-builder"
  check_gone aws rds describe-db-clusters --db-cluster-identifier "$RUN"
  n="$(aws apigatewayv2 get-apis --query "length(Items[?Name=='${RUN}'])" --output text)"
  echo "  HTTP APIs named ${RUN}: ${n}"; [ "$n" = 0 ] || left=1
  if aws iam list-attached-role-policies --role-name devin-cw-builder --query 'AttachedPolicies[].PolicyName' --output text | grep -qw "${RUN}-builder"; then
    echo "  still attached to devin-cw-builder: ${RUN}-builder"; left=1
  else
    echo "  not attached to devin-cw-builder: ${RUN}-builder"
  fi
  for fn in announcements preferences feedback; do check_gone aws lambda get-function --function-name "${RUN}-${fn}"; done
  check_gone aws secretsmanager describe-secret --secret-id "${RUN}/aurora/master"
  n="$(aws logs describe-log-groups --log-group-name-pattern "$RUN" --query 'length(logGroups)' --output text)"
  echo "  log groups matching ${RUN}: ${n}"; [ "$n" = 0 ] || left=1
  if [ "$left" = 0 ]; then echo "CLEAN: nothing tagged or named ${RUN} remains"; else echo "NOT CLEAN"; return 1; fi
}

case "$CMD" in
  up) cmd_up ;;
  replay) cmd_replay ;;
  status) cmd_status ;;
  reset) cmd_reset ;;
  down) cmd_down ;;
  verify-clean) cmd_verify_clean ;;
  *) die "usage: lp-serverless.sh up|replay|status|reset|down|verify-clean (RUN, CTX, STAGE from the environment)" ;;
esac
