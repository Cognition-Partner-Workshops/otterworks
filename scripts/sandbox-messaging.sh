#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Messaging reliability sandbox: plan, apply, drill, replay, reset, destroy and
# prove-clean for one run token, using the production module
# infrastructure/terraform/modules/messaging under new names.
#
#   RUN=rs-<yyyymmdd>-<xx> scripts/sandbox-messaging.sh <command>
#
#   plan          terraform plan for the token and check it only creates its own resources
#   up            plan, guard, then apply that exact plan (EXPIRES defaults to +24 h)
#   drill         after phase: reset, publish COUNT events, fail them all into the DLQ,
#                 prove the ledger is empty, then replay
#   replay        redrive the DLQ with StartMessageMoveTask, consume with one crash
#                 between each write and its ack, verify exactly-once
#   before-drill  before phase: show a failing event cycling past maxReceiveCount
#                 with nowhere to go
#   reset         purge the token's queues and empty its ledger
#   status        queue depths, redrive policies, alarm states
#   destroy       CONFIRM=<RUN> required; destroys both phases, then verify-clean
#   verify-clean  list anything still tagged run_token=<RUN> or named <RUN>-*
#
# PHASE=after (default) uses infrastructure/terraform/reliability-sandbox,
# PHASE=before uses its before/ twin (module pinned at c2332d0e, no DLQs).
# State and Terraform data live in STATE_DIR (default ~/.otterworks-sandbox),
# never in the repository. Assume the engineer role first:
#   source <(cloudworker/assume.sh engineer devin-<session id>)
# ------------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DRIVER="${SCRIPT_DIR}/lib/sandbox_messaging.py"
PYTHON="${PYTHON:-python3}"
TERRAFORM="${TERRAFORM:-terraform}"
AWS="${AWS:-aws}"
PHASE="${PHASE:-after}"
COUNT="${COUNT:-5}"
STATE_DIR="${STATE_DIR:-${HOME}/.otterworks-sandbox}"
export AWS_REGION="${AWS_REGION:-us-east-1}"

die() { echo "sandbox: $*" >&2; exit 2; }
log() { echo "[sandbox $(date -u +%H:%M:%SZ)] $*"; }

need_run() {
  [ -n "${RUN:-}" ] || die "RUN=rs-<yyyymmdd>-<xx> is required"
  [[ "$RUN" =~ ^rs-[0-9]{8}-[a-z]{2}$ ]] || die "RUN must look like rs-20261006-ab (got '${RUN}')"
  case "$PHASE" in
    after)  TF_DIR="${REPO_ROOT}/infrastructure/terraform/reliability-sandbox" ;;
    before) TF_DIR="${REPO_ROOT}/infrastructure/terraform/reliability-sandbox/before" ;;
    *) die "PHASE must be after or before" ;;
  esac
  mkdir -p "$STATE_DIR"
  local state_abs; state_abs="$(cd "$STATE_DIR" && pwd -P)"
  case "${state_abs}/" in "$(cd "$REPO_ROOT" && pwd -P)/"*) die "STATE_DIR must be outside the repository" ;; esac
  RUN_DIR="${state_abs}/${RUN}"
  mkdir -p "$RUN_DIR"
  export TF_DATA_DIR="${RUN_DIR}/.terraform-${PHASE}"
  STATE_FILE="${RUN_DIR}/${PHASE}.tfstate"
  OUTPUTS="${RUN_DIR}/${PHASE}-outputs.json"
  IDS="${RUN_DIR}/published-ids.json"
}

tf() { (cd "$TF_DIR" && "$TERRAFORM" "$@"); }

tf_init() { tf init -input=false -reconfigure -backend-config="path=${STATE_FILE}" >/dev/null; }

tf_vars() {
  EXPIRES="${EXPIRES:-$(date -u -d '+24 hours' +%Y-%m-%dT%H:%M:%SZ)}"
  TF_VARS=(-var "run_token=${RUN}" -var "expires=${EXPIRES}" -var "aws_region=${AWS_REGION}")
}

driver() { "$PYTHON" "$DRIVER" "$@"; }

guarded_plan() {
  local extra=("$@") plan="${RUN_DIR}/${PHASE}.tfplan" allow=()
  tf_init; tf_vars
  tf plan -input=false -out="$plan" "${TF_VARS[@]}" "${extra[@]}"
  tf show -json "$plan" > "${plan}.json"
  [ "${extra[*]:-}" = "-destroy" ] && allow=(--allow-delete)
  driver plan-guard --plan-json "${plan}.json" --run-token "$RUN" "${allow[@]}" \
    || die "plan touches something outside run token ${RUN}; nothing applied"
  PLAN_FILE="$plan"
}

save_outputs() { tf output -json > "$OUTPUTS"; }

need_outputs() {
  [ -s "$OUTPUTS" ] || { tf_init; save_outputs; }
  if ! { [ -s "$OUTPUTS" ] && grep -q '"run_token"' "$OUTPUTS"; }; then die "no outputs for ${RUN} (${PHASE}); run up first"; fi
}

cmd_plan() { need_run; guarded_plan; log "plan for ${RUN} (${PHASE}) is confined to the token: ${PLAN_FILE}"; }

cmd_up() {
  need_run; guarded_plan
  tf apply -input=false "$PLAN_FILE"
  save_outputs
  log "${RUN} (${PHASE}) is up, expires ${EXPIRES}; outputs in ${OUTPUTS}"
}

cmd_reset() { need_run; need_outputs; driver --outputs "$OUTPUTS" reset; rm -f "$IDS"; }

cmd_status() { need_run; need_outputs; driver --outputs "$OUTPUTS" status; }

cmd_replay() {
  need_run; [ "$PHASE" = after ] || die "replay needs PHASE=after (the before stack has no DLQ)"
  need_outputs; [ -s "$IDS" ] || die "no published ids for ${RUN}; run drill first"
  log "redriving the analytics DLQ back to its source queue"
  driver --outputs "$OUTPUTS" redrive
  log "consumer: apply each event, crash once before acking, then ack the redelivery as a duplicate"
  driver --outputs "$OUTPUTS" consume --crash-after-write --idle-seconds "${IDLE_SECONDS:-30}"
  log "verify: every published event applied exactly once, queues empty"
  driver --outputs "$OUTPUTS" verify --ids-file "$IDS"
}

cmd_drill() {
  need_run; [ "$PHASE" = after ] || die "drill needs PHASE=after; use before-drill for the before stack"
  need_outputs
  driver --outputs "$OUTPUTS" reset; rm -f "$IDS"
  log "SQS allows one purge per queue per 60 s; waiting before publishing"
  sleep "${PURGE_SETTLE_SECONDS:-60}"
  driver --outputs "$OUTPUTS" publish --count "$COUNT" --ids-file "$IDS"
  log "consumer with an injected ledger outage: every event fails until maxReceiveCount"
  driver --outputs "$OUTPUTS" consume --fault ledger --idle-seconds "${IDLE_SECONDS:-30}"
  driver --outputs "$OUTPUTS" wait-depth --queue analytics_dlq_url --expect "$COUNT" --timeout "${DLQ_WAIT_SECONDS:-300}"
  log "before recovery the business outcome is missing (verify is expected to fail here)"
  if driver --outputs "$OUTPUTS" verify --ids-file "$IDS"; then die "verify passed before recovery; the drill did not fail anything"; fi
  driver --outputs "$OUTPUTS" status
  cmd_replay
}

cmd_before_drill() {
  [ "$PHASE" = before ] || die "before-drill needs PHASE=before"
  need_run; need_outputs
  driver --outputs "$OUTPUTS" reset; rm -f "$IDS"
  sleep "${PURGE_SETTLE_SECONDS:-60}"
  driver --outputs "$OUTPUTS" publish --count 1 --ids-file "$IDS"
  log "failing consumer for ${BEFORE_SECONDS:-90} s: receive count climbs past 5, nothing captures it"
  driver --outputs "$OUTPUTS" consume --fault ledger --idle-seconds 20 --max-seconds "${BEFORE_SECONDS:-90}"
  driver --outputs "$OUTPUTS" status
}

cmd_destroy() {
  need_run
  [ "${CONFIRM:-}" = "$RUN" ] || die "destroy needs CONFIRM=${RUN}"
  local p
  for p in before after; do
    PHASE="$p"; need_run
    [ -s "$STATE_FILE" ] || { log "no ${p} state for ${RUN}"; continue; }
    guarded_plan -destroy
    tf apply -input=false "$PLAN_FILE"
    rm -f "$OUTPUTS"
  done
  cmd_verify_clean
}

cmd_verify_clean() {
  need_run
  local deadline=$(( $(date +%s) + ${VERIFY_WAIT_SECONDS:-300} )) left arns
  while :; do
    left=0
    arns="$("$AWS" resourcegroupstaggingapi get-resources --tag-filters "Key=run_token,Values=${RUN}" \
      --query 'ResourceTagMappingList[].ResourceARN' --output text)"
    [ -z "$arns" ] || [ "$arns" = None ] || left=1
    [ "$left" = 0 ] || [ "$(date +%s)" -ge "$deadline" ] && break
    log "tagging API still lists resources for ${RUN}; it can trail deletes, retrying in 30 s"
    sleep 30
  done
  echo "tagging API run_token=${RUN}: $([ "$left" = 0 ] && echo 0 resources || echo "$arns")"
  local q t a
  q="$("$AWS" sqs list-queues --queue-name-prefix "$RUN" --query 'QueueUrls' --output text)"
  t="$("$AWS" sns list-topics --query "Topics[?contains(TopicArn, ':${RUN}')].TopicArn" --output text)"
  a="$("$AWS" cloudwatch describe-alarms --alarm-name-prefix "$RUN" --query 'MetricAlarms[].AlarmName' --output text)"
  local tables; tables="$("$AWS" dynamodb list-tables --query "TableNames[?starts_with(@, '${RUN}')]" --output text)"
  for kind in "SQS queues:$q" "SNS topics:$t" "alarms:$a" "DynamoDB tables:$tables"; do
    local v="${kind#*:}"
    if [ -z "$v" ] || [ "$v" = None ]; then echo "  ${kind%%:*} named ${RUN}*: none"; else echo "  ${kind%%:*} named ${RUN}*: ${v}"; left=1; fi
  done
  [ "$left" = 0 ] || { echo "sandbox ${RUN} is NOT clean"; return 1; }
  echo "sandbox ${RUN} is clean"
}

case "${1:-}" in
  plan) cmd_plan ;;
  up) cmd_up ;;
  drill) cmd_drill ;;
  replay) cmd_replay ;;
  before-drill) cmd_before_drill ;;
  reset) cmd_reset ;;
  status) cmd_status ;;
  destroy) cmd_destroy ;;
  verify-clean) cmd_verify_clean ;;
  *) sed -n '2,32p' "$0"; exit 2 ;;
esac
