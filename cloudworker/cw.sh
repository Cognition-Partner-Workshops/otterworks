#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/.." && pwd)"
STATE="${HERE}/.state"
OUTPUTS="${STATE}/outputs.json"
STATE_FILE="${STATE}/state.json"
READER_FILE="${STATE}/devin-cw-reader.json"
TF_DIR="${REPO}/infrastructure/terraform/cloud-worker"
EVENTING_ENV="${REPO}/infrastructure/helm/tenant-values/cloud-worker/eventing.env"
RBAC="${HERE}/k8s/rbac.yaml"
AWS_AUTH="${HERE}/aws-auth.sh"
SIMULATE="${HERE}/simulate.py"
SCENARIO="${HERE}/scenario.yaml"

export AWS_REGION="${AWS_REGION:-us-east-1}"
NS="otterworks-cloud-worker"
TENANT="cloud-worker"
QUEUE="otterworks-cw-notifications"
DLQ="otterworks-cw-notifications-dlq"
TABLE="otterworks-cw-notifications"
ALARM="otterworks-cw-notifications-dlq-depth"
TOPIC="otterworks-cw-events"
READER_USER="devin-cw-reader"
DRIFT_RETENTION=1209600
GSI="userId-createdAt-index"
LOG_WINDOW="15m"
LAND_SECONDS="${CW_LAND_SECONDS:-90}"
SETTLE_SECONDS="${CW_SETTLE_SECONDS:-120}"
GH_REPO="${CW_GH_REPO:-Cognition-Partner-Workshops/otterworks}"
DRY="${CW_DRY_RUN:-0}"
FAULT="${CW_FAULT:-}"
PAGE="${CW_PAGE:-1}"

OUTPUT_NAMES=(
  sns_topic_arn sqs_queue_url sqs_queue_arn sqs_dlq_url sqs_dlq_arn dynamodb_table
  irsa_notification_service_role_arn irsa_file_service_role_arn
  devin_observer_role_arn devin_builder_role_arn devin_reader_user_name
  alarm_name dashboard_url eventbridge_rule_name
)

log() { echo "cw: $*" >&2; }
die() { echo "cw: error: $*" >&2; exit 1; }
exec 3>&2
show() { { printf '+'; printf ' %q' "$@"; printf '\n'; } >&3; }

run() {
  show "$@"
  [ "${DRY}" = 1 ] && return 0
  "$@"
}

read_cmd() {
  if [ "${DRY}" = 1 ]; then show "$@"; return 0; fi
  "$@"
}

usage() {
  cat >&2 <<'USAGE'
usage: cloudworker/cw.sh <verb> [args]
  up                     provision infra, map roles, plant drift, wire tenant, smoke test
  apply                  re-render tenant eventing config from eventing.env
  credentials            rotate the devin-cw-reader access key into .state/
  arm [--fault NAME]     plant a fault from scenario.yaml (default table) and publish six events
  status [--json]        tenant, config, image, queues, alarm, rule, helm history, demo state
  verify before|after [--fault NAME]
                         gate the demo state (also EXPECT=before|after, FAULT=NAME)
  simulate [--count N]   publish file_shared events (also COUNT=N)
  quiet [MINUTES]        disable alarm actions for a while (default 10)
  disarm                 quiet, apply, purge queues, reset alarm, re-enable actions
  reset [--scope run]    disarm, close demo-cw-* PRs and branches, drop cw-* tenants, re-plant drift;
                         --scope run only touches branches and tenants created since the arm
  teardown               reset, unmap roles, delete RBAC and keys, destroy infra
  trail                  CloudTrail events from devin-cw-* identities in the last 2 h
CW_DRY_RUN=1 prints every command instead of running it.
CW_PAGE=0 makes arm, disarm and reset leave the EventBridge rule as they find it.
USAGE
}

caller_arn() {
  aws sts get-caller-identity --query Arn --output text 2>/dev/null || true
}

require_operator() {
  [ "${DRY}" = 1 ] && return 0
  local arn; arn="$(caller_arn)"
  [ -n "${arn}" ] || die "no AWS credentials; export the operator's credentials"
  case "${arn}" in
    *:assumed-role/devin-cw-*|*:user/devin-cw-*) die "this verb needs the operator's credentials, not ${arn##*/}" ;;
  esac
}

account_id() {
  if [ -n "${AWS_ACCOUNT_ID:-}" ]; then printf '%s' "${AWS_ACCOUNT_ID}"; return; fi
  if [ "${DRY}" = 1 ]; then printf '%s' "\${AWS_ACCOUNT_ID}"; return; fi
  aws sts get-caller-identity --query Account --output text
}

ensure_account() {
  AWS_ACCOUNT_ID="$(account_id)"
  [ -n "${AWS_ACCOUNT_ID}" ] || die "cannot resolve the AWS account"
}

eventing_value() {
  local key=$1
  [ -f "${EVENTING_ENV}" ] || die "missing ${EVENTING_ENV#"${REPO}/"}"
  (
    set +u
    # shellcheck source=/dev/null
    . "${EVENTING_ENV}"
    printf '%s' "${!key:-}"
  )
}

scenario_get() {  # dotted path; prints a scalar, key=value per map entry, or one line per list item
  python3 - "${SCENARIO}" "$1" <<'PY'
import sys
import yaml

node = yaml.safe_load(open(sys.argv[1]))
for part in sys.argv[2].split("."):
    node = node.get(part) if isinstance(node, dict) else None
    if node is None:
        sys.exit(0)
if isinstance(node, dict):
    for key, value in node.items():
        print(f"{key}={value}")
elif isinstance(node, list):
    for value in node:
        print(value)
elif isinstance(node, bool):
    print(str(node).lower())
else:
    print(node)
PY
}

parse_fault() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --fault) FAULT="${2:-}"; shift 2 ;;
      --fault=*|FAULT=*) FAULT="${1#*=}"; shift ;;
      *) die "unexpected argument: $1" ;;
    esac
  done
  [ -n "${FAULT}" ] || FAULT="$(scenario_get default_fault)"
  [ -n "${FAULT}" ] || die "scenario.yaml has no default_fault"
  [ -n "$(scenario_get "faults.${FAULT}.release")" ] \
    || die "unknown fault ${FAULT}; scenario.yaml faults: $(scenario_get faults | cut -d= -f1 | tr '\n' ' ')"
}

fault_get() { scenario_get "faults.${FAULT}.$1"; }

outputs_load() {
  [ -s "${OUTPUTS}" ] && return 0
  [ "${DRY}" = 1 ] && return 0
  [ -d "${TF_DIR}" ] || return 0
  if [ ! -d "${TF_DIR}/.terraform" ]; then
    terraform -chdir="${TF_DIR}" init -input=false >/dev/null 2>&1 || true
  fi
  local json='{}' name val found=false
  for name in "${OUTPUT_NAMES[@]}"; do
    val="$(terraform -chdir="${TF_DIR}" output -raw "${name}" 2>/dev/null)" || val=""
    [ -n "${val}" ] && found=true
    json="$(jq -c --arg k "${name}" --arg v "${val}" '. + {($k): $v}' <<<"${json}")"
  done
  if [ "${found}" = true ]; then
    mkdir -p "${STATE}"
    printf '%s\n' "${json}" >"${OUTPUTS}"
  fi
}

output_fallback() {
  case "$1" in
    sqs_queue_url) aws sqs get-queue-url --queue-name "${QUEUE}" --query QueueUrl --output text 2>/dev/null || true ;;
    sqs_dlq_url) aws sqs get-queue-url --queue-name "${DLQ}" --query QueueUrl --output text 2>/dev/null || true ;;
    sns_topic_arn) ensure_account; printf 'arn:aws:sns:%s:%s:%s' "${AWS_REGION}" "${AWS_ACCOUNT_ID}" "${TOPIC}" ;;
    dynamodb_table) printf '%s' "${TABLE}" ;;
    alarm_name) printf '%s' "${ALARM}" ;;
    devin_reader_user_name) printf '%s' "${READER_USER}" ;;
    devin_observer_role_arn) aws iam get-role --role-name devin-cw-observer --query Role.Arn --output text 2>/dev/null || true ;;
    devin_builder_role_arn) aws iam get-role --role-name devin-cw-builder --query Role.Arn --output text 2>/dev/null || true ;;
  esac
}

out() {
  local name=$1 val=""
  outputs_load
  if [ -s "${OUTPUTS}" ]; then
    val="$(jq -r --arg k "${name}" '.[$k] // empty' "${OUTPUTS}")"
  fi
  if [ -z "${val}" ]; then
    if [ "${DRY}" = 1 ]; then val="<${name}>"; else val="$(output_fallback "${name}")"; fi
  fi
  [ -n "${val}" ] || die "Terraform output ${name} is unavailable; run cw.sh up"
  printf '%s' "${val}"
}

state_get() {
  if [ -f "${STATE_FILE}" ]; then jq -r --arg k "$1" '.[$k] // empty' "${STATE_FILE}"; fi
}

state_set() {
  show state "$1=$2"
  [ "${DRY}" = 1 ] && return 0
  mkdir -p "${STATE}"
  local cur='{}'
  [ -f "${STATE_FILE}" ] && cur="$(cat "${STATE_FILE}")"
  jq --arg k "$1" --arg v "$2" '.[$k] = $v' <<<"${cur}" >"${STATE_FILE}.tmp"
  mv "${STATE_FILE}.tmp" "${STATE_FILE}"
}

state_del() {
  show state "unset $1"
  [ "${DRY}" = 1 ] && return 0
  [ -f "${STATE_FILE}" ] || return 0
  jq --arg k "$1" 'del(.[$k])' "${STATE_FILE}" >"${STATE_FILE}.tmp"
  mv "${STATE_FILE}.tmp" "${STATE_FILE}"
}

queue_depth() {
  local url=$1
  read_cmd aws sqs get-queue-attributes --queue-url "${url}" \
    --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
    --query 'Attributes.[ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible]' \
    --output text 2>/dev/null || true
}

alarm_state() {
  read_cmd aws cloudwatch describe-alarms --alarm-names "$(out alarm_name)" \
    --query 'MetricAlarms[0].[StateValue,ActionsEnabled]' --output text 2>/dev/null || true
}

rule_state() {
  read_cmd aws events describe-rule --name "$(out eventbridge_rule_name)" \
    --query State --output text 2>/dev/null || true
}

enable_rule() {
  if [ "${PAGE}" = 0 ]; then
    log "CW_PAGE=0: leaving EventBridge rule $(out eventbridge_rule_name) $(rule_state)"
  else
    run aws events enable-rule --name "$(out eventbridge_rule_name)"
  fi
}

queue_config() {  # MessageRetentionPeriod VisibilityTimeout maxReceiveCount
  local attrs
  attrs="$(read_cmd aws sqs get-queue-attributes --queue-url "$(out sqs_queue_url)" \
    --attribute-names MessageRetentionPeriod VisibilityTimeout RedrivePolicy --output json 2>/dev/null || true)"
  [ -n "${attrs}" ] || return 0
  jq -r '.Attributes | [.MessageRetentionPeriod, .VisibilityTimeout,
    ((.RedrivePolicy // "{}") | fromjson | .maxReceiveCount // "" | tostring)] | join(" ")' <<<"${attrs}" 2>/dev/null || true
}

running_image() {
  read_cmd kubectl -n "${NS}" get deploy notification-service \
    -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true
}

live_table() {
  read_cmd kubectl -n "${NS}" get configmap notification-service-config \
    -o jsonpath='{.data.DYNAMODB_TABLE_NOTIFICATIONS}' 2>/dev/null || true
}

live_preferences_table() {
  read_cmd kubectl -n "${NS}" get configmap notification-service-config \
    -o jsonpath='{.data.DYNAMODB_TABLE_PREFERENCES}' 2>/dev/null || true
}

git_table() { eventing_value DDB_NOTIF; }

namespace_exists() {
  [ "${DRY}" = 1 ] && { show kubectl get namespace "${NS}"; return 0; }
  kubectl get namespace "${NS}" >/dev/null 2>&1
}

dns_filters() {  # add|remove the tenant's apex hosts in external-dns's domain filters
  local verb="$1" current new want
  want="$(printf -- '--domain-filter=%s\n' "t-${TENANT}.otterworks.app" "api-t-${TENANT}.otterworks.app" | jq -Rsc 'split("\n")[:-1]')"
  if [ "${DRY}" = 1 ]; then show kubectl patch deploy external-dns -n external-dns --type=json -p "[${verb} ${want}]"; return 0; fi
  current="$(kubectl get deploy external-dns -n external-dns -o json 2>/dev/null | jq -c '.spec.template.spec.containers[0].args')" \
    || { log "external-dns not found; tenant hosts need DNS by hand"; return 0; }
  new="$(jq -c --argjson want "${want}" --arg verb "${verb}" 'if $verb == "add" then . + ($want - .) else . - $want end' <<<"${current}")"
  [ "${new}" = "${current}" ] && return 0
  run kubectl patch deploy external-dns -n external-dns --type=json \
    -p "[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/args\",\"value\":${new}}]"
  run kubectl rollout status deploy external-dns -n external-dns --timeout=120s
}

restart_and_wait() {
  local d
  for d in "$@"; do run kubectl -n "${NS}" rollout restart "deploy/${d}"; done
  for d in "$@"; do run kubectl -n "${NS}" rollout status "deploy/${d}" --timeout=240s; done
}

simulate() {
  run python3 "${SIMULATE}" --count "$1" --topic-arn "$(out sns_topic_arn)" --region "${AWS_REGION}"
}

webhook_env() {
  local file="${CW_WEBHOOK_FILE:-${HOME}/.cw-webhook.json}"
  if [ -f "${file}" ]; then
    TF_VAR_devin_webhook_url="$(jq -r '.url // empty' "${file}")"
    TF_VAR_devin_webhook_secret="$(jq -r '.secret // empty' "${file}")"
    if [ -z "${TF_VAR_devin_webhook_url}" ] || [ -z "${TF_VAR_devin_webhook_secret}" ]; then
      die "${file} needs both url and secret"
    fi
    export TF_VAR_devin_webhook_url TF_VAR_devin_webhook_secret
    log "webhook url and secret from ${file}"
  else
    log "no ${file}; Terraform uses its placeholder webhook"
  fi
}

wait_dlq_zero() {
  local url; url="$(out sqs_dlq_url)"
  log "watching ${DLQ} for ${SETTLE_SECONDS}s"
  if [ "${DRY}" = 1 ]; then queue_depth "${url}" >/dev/null; return 0; fi
  local waited=0 depth
  while [ "${waited}" -lt "${SETTLE_SECONDS}" ]; do
    depth="$(queue_depth "${url}" | awk '{print $1 + $2}')"
    [ "${depth:-0}" -eq 0 ] || die "${DLQ} has ${depth} message(s) after ${waited}s"
    sleep 10; waited=$((waited + 10))
  done
  log "${DLQ} stayed at 0"
}

wait_queues_empty() {
  local q d; q="$(out sqs_queue_url)"; d="$(out sqs_dlq_url)"
  if [ "${DRY}" = 1 ]; then queue_depth "${q}" >/dev/null; queue_depth "${d}" >/dev/null; return 0; fi
  local waited=0 total
  while :; do
    total="$( { queue_depth "${q}"; queue_depth "${d}"; } | awk '{s += $1 + $2} END {print s + 0}')"
    [ "${total}" -eq 0 ] && { log "both queues are empty"; return 0; }
    [ "${waited}" -ge 180 ] && die "queues still hold ${total} message(s) after 180s"
    sleep 10; waited=$((waited + 10))
  done
}

delete_reader_keys() {
  local user=$1 keys k
  keys="$(read_cmd aws iam list-access-keys --user-name "${user}" \
    --query 'AccessKeyMetadata[].AccessKeyId' --output text 2>/dev/null || true)"
  for k in ${keys}; do
    [ "${k}" = None ] && continue
    run aws iam delete-access-key --user-name "${user}" --access-key-id "${k}"
  done
}

notification_eventing_args() {
  local prefs; prefs="$(eventing_value DDB_NOTIF_PREFS)"
  [ -n "${prefs}" ] || die "eventing.env has no DDB_NOTIF_PREFS"
  printf '%s\n' \
    --set-string "config.SNS_TOPIC_ARN=$(eventing_value SNS_TOPIC)" \
    --set-string "config.SQS_QUEUE_URL=$(eventing_value SQS_NOTIF)" \
    --set-string "config.DYNAMODB_TABLE_NOTIFICATIONS=$(eventing_value DDB_NOTIF)" \
    --set-string "config.DYNAMODB_TABLE_PREFERENCES=${prefs}" \
    --set-string "serviceAccount.roleArn=$(eventing_value IRSA_notification_service)"
}

cmd_apply() {
  ensure_account
  local sns irsa_file
  sns="$(eventing_value SNS_TOPIC)"
  irsa_file="$(eventing_value IRSA_file_service)"
  local -a notif_args image_args=()
  mapfile -t notif_args < <(notification_eventing_args)
  [ "${#notif_args[@]}" -gt 0 ] || die "cannot read eventing.env"
  local baseline; baseline="$(state_get baseline_image)"
  if [ -n "${baseline}" ]; then
    image_args=(--set-string "image.tag=${baseline}")
    log "notification-service image back to ${baseline%%@*}"
  fi
  run helm upgrade notification-service "${REPO}/infrastructure/helm/notification-service" -n "${NS}" --reuse-values \
    "${notif_args[@]}" "${image_args[@]}"
  run helm upgrade file-service "${REPO}/infrastructure/helm/file-service" -n "${NS}" --reuse-values \
    --set-string "config.SNS_TOPIC_ARN=${sns}" \
    --set-string "serviceAccount.roleArn=${irsa_file}"
  restart_and_wait notification-service file-service
  log "applied eventing.env to ${NS}"
}

cmd_up() {
  require_operator
  webhook_env
  run terraform -chdir="${TF_DIR}" init -input=false
  run terraform -chdir="${TF_DIR}" apply -input=false -auto-approve
  run rm -f "${OUTPUTS}"
  run bash "${AWS_AUTH}" add "$(out devin_observer_role_arn)" "$(out devin_builder_role_arn)"
  run kubectl apply -f "${RBAC}"
  dns_filters add
  run aws sqs set-queue-attributes --queue-url "$(out sqs_queue_url)" \
    --attributes "MessageRetentionPeriod=${DRIFT_RETENTION}"
  if namespace_exists; then
    cmd_apply
  else
    log "namespace ${NS} not found; push demo-cloud-worker to deploy it, then run cw.sh apply"
  fi
  simulate 1
  wait_dlq_zero
  log "up complete"
}

cmd_credentials() {
  require_operator
  local user observer builder
  user="$(out devin_reader_user_name)"
  observer="$(out devin_observer_role_arn)"
  builder="$(out devin_builder_role_arn)"
  delete_reader_keys "${user}"
  show aws iam create-access-key --user-name "${user}" '>' "${READER_FILE}"
  [ "${DRY}" = 1 ] && return 0
  mkdir -p "${STATE}"
  (
    umask 077
    aws iam create-access-key --user-name "${user}" --output json \
      | jq --arg o "${observer}" --arg b "${builder}" '{
          CW_AWS_ACCESS_KEY_ID: .AccessKey.AccessKeyId,
          CW_AWS_SECRET_ACCESS_KEY: .AccessKey.SecretAccessKey,
          CW_OBSERVER_ROLE_ARN: $o,
          CW_BUILDER_ROLE_ARN: $b}' >"${READER_FILE}.tmp"
  )
  mv "${READER_FILE}.tmp" "${READER_FILE}"
  chmod 600 "${READER_FILE}"
  log "wrote ${READER_FILE#"${REPO}/"} (mode 600) with a new key for ${user}"
}

release_image_ref() {  # tag@digest of the fault's release image, or nothing when the fault keeps the image
  local tag repo digest
  tag="$(fault_get image_tag)"
  [ -n "${tag}" ] || return 0
  repo="$(fault_get image_repository)"
  if [ "${DRY}" = 1 ]; then
    show aws ecr describe-images --repository-name "${repo}" --image-ids "imageTag=${tag}"
    printf '%s' "${tag}"; return 0
  fi
  digest="$(aws ecr describe-images --repository-name "${repo}" --image-ids "imageTag=${tag}" \
    --query 'imageDetails[0].imageDigest' --output text 2>/dev/null || true)"
  case "${digest}" in sha256:*) ;; *) die "image ${repo}:${tag} is not in ECR; push $(fault_get release_branch) and wait for CD" ;; esac
  printf '%s@%s' "${tag}" "${digest}"
}

cmd_arm() {
  parse_fault "$@"
  require_operator
  ensure_account
  local -a set_args=()
  local kv image
  while IFS= read -r kv; do
    [ -n "${kv}" ] && set_args+=(--set-string "${kv}")
  done < <(fault_get set)
  if [ "$(fault_get config_vs_git)" = equals ]; then
    local -a notif_args
    mapfile -t notif_args < <(notification_eventing_args)
    [ "${#notif_args[@]}" -gt 0 ] || die "cannot read eventing.env"
    set_args+=("${notif_args[@]}")
  fi
  image="$(release_image_ref)"
  [ -n "${image}" ] && set_args+=(--set-string "image.tag=${image}")
  log "arming fault ${FAULT}"
  run aws cloudwatch enable-alarm-actions --alarm-names "$(out alarm_name)"
  enable_rule
  if [ -z "$(state_get baseline_image)" ]; then
    local tag; tag="$(read_cmd helm -n "${NS}" get values notification-service -o json | jq -r '.image.tag // empty')"
    [ -n "${tag}" ] && state_set baseline_image "${tag}"
  fi
  if [ "$(fault_get align_queue_with_terraform)" = true ]; then
    run aws sqs set-queue-attributes --queue-url "$(out sqs_queue_url)" \
      --attributes "MessageRetentionPeriod=$(scenario_get drift.terraform_value)"
  fi
  run helm upgrade notification-service "${REPO}/infrastructure/helm/notification-service" -n "${NS}" --reuse-values \
    "${set_args[@]}"
  restart_and_wait notification-service
  # Keep node consolidation from evicting the pod, and its parse-failure log, mid-demo.
  run kubectl -n "${NS}" annotate pod -l app.kubernetes.io/name=notification-service \
    karpenter.sh/do-not-disrupt=true --overwrite
  simulate "$(fault_get events_published)"
  local now; now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  state_set armed_at "${now}"
  state_set armed_fault "${FAULT}"
  state_del quiet_until
  echo "armed ${FAULT} at ${now}"
  fault_get timeline | sed 's/^/  /'
}

status_json() {
  local live git prefs_live prefs_git qd dd alarm armed quiet image rule qc fault
  live="$(live_table)"
  git="$(git_table)"
  prefs_live="$(live_preferences_table)"
  prefs_git="$(eventing_value DDB_NOTIF_PREFS)"
  qd="$(queue_depth "$(out sqs_queue_url)")"
  dd="$(queue_depth "$(out sqs_dlq_url)")"
  alarm="$(alarm_state)"
  image="$(running_image)"
  rule="$(rule_state)"
  qc="$(queue_config)"
  local tmp; tmp="$(mktemp -d)"
  read_cmd kubectl -n "${NS}" get pods -o json >"${tmp}/pods.json" 2>/dev/null || true
  read_cmd helm history notification-service -n "${NS}" -o json >"${tmp}/helm.json" 2>/dev/null || true
  armed="$(state_get armed_at)"
  quiet="$(state_get quiet_until)"
  fault="$(state_get armed_fault)"
  jq -n \
    --arg ns "${NS}" --arg live "${live}" --arg git "${git}" \
    --arg prefs_live "${prefs_live}" --arg prefs_git "${prefs_git}" \
    --arg qd "${qd}" --arg dd "${dd}" --arg alarm "${alarm}" \
    --rawfile pods "${tmp}/pods.json" --rawfile helm "${tmp}/helm.json" \
    --arg armed "${armed}" --arg quiet "${quiet}" --arg fault "${fault}" \
    --arg image "${image}" --arg baseline "$(state_get baseline_image)" --arg rule "${rule}" \
    --arg qc "${qc}" --arg retention_tf "$(scenario_get drift.terraform_value)" '
    def num: if . == "" or . == null or . == "None" then null else tonumber end;
    def nz: if . == "" or . == "None" then null else . end;
    {
      namespace: $ns,
      pods: (if $pods == "" then null else [($pods | fromjson).items[] | {
        name: .metadata.name,
        phase: .status.phase,
        ready: ([.status.containerStatuses[]?.ready] | length > 0 and all),
        restarts: ([.status.containerStatuses[]?.restartCount] | add // 0)}] end),
      table: {live: ($live | nz), git: ($git | nz), drift: ($live != "" and $live != $git)},
      preferences_table: {live: ($prefs_live | nz), git: ($prefs_git | nz), drift: ($prefs_live != "" and $prefs_live != $prefs_git)},
      queue: ($qd | split("\t") | {visible: (.[0] | num), in_flight: (.[1] | num)}),
      dlq: ($dd | split("\t") | {visible: (.[0] | num), in_flight: (.[1] | num)}),
      queue_config: ($qc | split(" ") | {retention: (.[0] | num), retention_terraform: ($retention_tf | num),
        visibility_timeout: (.[1] | num), max_receive_count: (.[2] | num)}),
      image: {running: ($image | nz), tag: ($image | nz | if . == null then null else (split("/") | last | split("@")[0]) end),
        baseline: ($baseline | nz)},
      eventbridge_rule: ($rule | nz),
      alarm: ($alarm | split("\t") | {state: (.[0] | nz), actions_enabled: (if .[1] == null then null else (.[1] == "True") end)}),
      helm: (if $helm == "" then null else ($helm | fromjson) as $h
        | {revisions: ($h | length), last_description: ($h | last | .description)} end),
      armed_at: ($armed | nz),
      armed_fault: ($fault | nz),
      quiet_until: ($quiet | nz)
    }'
  rm -rf "${tmp}"
}

cmd_status() {
  local json; json="$(status_json)"
  if [ "${1:-}" = "--json" ]; then printf '%s\n' "${json}"; return 0; fi
  jq -r '
    def v: if . == null then "unknown" else tostring end;
    "namespace      \(.namespace)",
    "pods           \(if .pods == null then "unknown" else ([.pods[] | "\(.name) \(if .ready then "ready" else .phase end)"] | join(", ")) end)",
    "table live     \(.table.live | v)",
    "table git      \(.table.git | v)\(if .table.drift then "  (drift)" else "" end)",
    "prefs live     \(.preferences_table.live | v)",
    "prefs git      \(.preferences_table.git | v)\(if .preferences_table.drift then "  (drift)" else "" end)",
    "queue          \(.queue.visible | v) visible, \(.queue.in_flight | v) in flight",
    "dlq            \(.dlq.visible | v) visible, \(.dlq.in_flight | v) in flight",
    "retention      \(.queue_config.retention | v)s, terraform \(.queue_config.retention_terraform | v)s\(if .queue_config.retention != null and .queue_config.retention != .queue_config.retention_terraform then "  (drift)" else "" end)",
    "image          \(.image.tag | v)",
    "alarm          \(.alarm.state | v), actions \(if .alarm.actions_enabled == true then "enabled" elif .alarm.actions_enabled == false then "disabled" else "unknown" end)",
    "rule           \(.eventbridge_rule | v)",
    "helm           \(if .helm == null then "unavailable" else "\(.helm.revisions) revisions, last: \(.helm.last_description)" end)",
    "armed_at       \(.armed_at // "-")\(if .armed_fault then " (\(.armed_fault))" else "" end)",
    "quiet_until    \(.quiet_until // "-")"
  ' <<<"${json}"
}

VERIFY_FAILS=0
VERIFY_TOTAL=0
check() {
  local result=$1 name=$2 measured=$3
  VERIFY_TOTAL=$((VERIFY_TOTAL + 1))
  if [ "${DRY}" = 1 ]; then result=SKIP
  elif [ "${result}" != PASS ]; then VERIFY_FAILS=$((VERIFY_FAILS + 1)); fi
  printf '%-4s  %-36s %s\n' "${result}" "${name}" "${measured}"
}

pf() { if "$@"; then echo PASS; else echo FAIL; fi; }

dlq_visible() { queue_depth "$(out sqs_dlq_url)" | awk '{print $1}'; }

log_count() {
  local logs
  logs="$(read_cmd kubectl -n "${NS}" logs -l app.kubernetes.io/name=notification-service \
    --since="${LOG_WINDOW}" --tail=-1 --all-containers 2>/dev/null || true)"
  grep -cF -- "$1" <<<"${logs}" || true
}

config_matches_git() {  # prints the measured values; returns 0 when tables and queue attributes equal git
  local live=$1 git=$2 prefs_live prefs_git qc ret vis mrc want_ret want_vis want_mrc
  prefs_live="$(live_preferences_table)"; prefs_git="$(eventing_value DDB_NOTIF_PREFS)"
  qc="$(queue_config)"; read -r ret vis mrc <<<"${qc}"
  want_ret="$(scenario_get drift.terraform_value)"
  want_vis="$(scenario_get thresholds.visibility_timeout_seconds)"
  want_mrc="$(scenario_get thresholds.max_receive_count)"
  echo "table=${live:-unknown} prefs=${prefs_live:-unknown} retention=${ret:-unknown} visibility=${vis:-unknown} maxReceive=${mrc:-unknown}"
  [ -n "${live}" ] && [ "${live}" = "${git}" ] && [ -n "${prefs_live}" ] && [ "${prefs_live}" = "${prefs_git}" ] \
    && [ "${ret:-}" = "${want_ret}" ] && [ "${vis:-}" = "${want_vis}" ] && [ "${mrc:-}" = "${want_mrc}" ]
}

deploys_ready() {
  local json
  json="$(read_cmd kubectl -n "${NS}" get deploy -o json 2>/dev/null || true)"
  [ -n "${json}" ] || return 0
  jq -r '(.items | map({key: .metadata.name, value: .}) | from_entries) as $d
    | ["notification-service", "file-service"]
    | map(if $d[.] then "\(.) \($d[.].status.readyReplicas // 0)/\($d[.].spec.replicas // 1)" else "\(.) missing" end)
    | join(", ")' <<<"${json}" 2>/dev/null || true
}

all_ready() {
  local s=$1
  [ -n "${s}" ] || return 1
  case "${s}" in *missing*) return 1 ;; esac
  awk -v RS=', ' 'NF {count++; split($2, r, "/"); if (r[1] + 0 < r[2] + 0 || r[2] + 0 == 0) bad = 1} END {exit (bad || count != 2)}' <<<"${s}"
}

landing_check() {
  local published file_id user table waited=0 count
  table="$(out dynamodb_table)"
  if [ "${DRY}" = 1 ]; then
    simulate 1
    show aws dynamodb query --table-name "${table}" --index-name "${GSI}" \
      --key-condition-expression 'userId = :u' --filter-expression 'resourceId = :f' --select COUNT
    check SKIP "simulated event lands in ${table}" "within ${LAND_SECONDS}s"
    return 0
  fi
  if ! published="$(python3 "${SIMULATE}" --count 1 --topic-arn "$(out sns_topic_arn)" --region "${AWS_REGION}" 2>&1)"; then
    check FAIL "simulated event lands in ${table}" "publish failed: $(tail -n 1 <<<"${published}")"
    return 0
  fi
  published="$(tail -n 1 <<<"${published}")"
  file_id="$(jq -r .fileId <<<"${published}")"
  user="$(jq -r .userId <<<"${published}")"
  while :; do
    count="$(aws dynamodb query --table-name "${table}" --index-name "${GSI}" \
      --key-condition-expression 'userId = :u' --filter-expression 'resourceId = :f' \
      --expression-attribute-values "{\":u\":{\"S\":\"${user}\"},\":f\":{\"S\":\"${file_id}\"}}" \
      --select COUNT --query Count --output text 2>/dev/null || echo 0)"
    if [ "${count:-0}" -gt 0 ]; then
      check PASS "simulated event lands in ${table}" "file ${file_id} after ${waited}s"
      return 0
    fi
    [ "${waited}" -ge "${LAND_SECONDS}" ] && break
    sleep 5; waited=$((waited + 5))
  done
  check FAIL "simulated event lands in ${table}" "file ${file_id} not found after ${LAND_SECONDS}s"
}

cmd_verify() {
  local expect=${1:-${EXPECT:-}}
  [ $# -gt 0 ] && shift
  expect="${expect#EXPECT=}"
  case "${expect}" in before|after) ;; *) die "usage: cw.sh verify before|after [--fault NAME]" ;; esac
  parse_fault "$@"
  ensure_account
  local verify_label=""
  if [ "${expect}" = before ] && [ "${FAULT}" != "$(scenario_get default_fault)" ]; then verify_label=" (${FAULT})"; fi
  local live git dlq alarm
  live="$(live_table)"; git="$(git_table)"
  dlq="$(dlq_visible)"; dlq="${dlq:-unknown}"
  alarm="$(alarm_state | awk '{print $1}')"; alarm="${alarm:-unknown}"
  if [ "${expect}" = before ]; then
    local pattern hits measured result
    pattern="$(fault_get log_pattern)"
    [ -n "${pattern}" ] || die "fault ${FAULT} has no log_pattern"
    hits="$(log_count "${pattern}")"
    if [ "$(fault_get config_vs_git)" = equals ]; then
      if measured="$(config_matches_git "${live}" "${git}")"; then result=PASS; else result=FAIL; fi
      check "${result}" "config equals git" "${measured}"
    else
      check "$(pf test -n "${live}" -a "${live}" != "${git}")" "live table differs from git" "live=${live:-unknown} git=${git}"
    fi
    check "$(pf test "${dlq}" != unknown -a "${dlq}" -ge 1 2>/dev/null)" "DLQ depth >= 1" "${dlq}"
    check "$(pf test "${alarm}" = ALARM)" "alarm state ALARM" "${alarm}"
    check "$(pf test "${hits:-0}" -ge 1)" "${pattern} in ${LOG_WINDOW}" "${hits:-0}"
  else
    local ready; ready="$(deploys_ready)"
    check "$(pf test -n "${live}" -a "${live}" = "${git}")" "live table equals git" "live=${live:-unknown} git=${git}"
    check "$(pf test "${dlq}" = 0)" "DLQ depth == 0" "${dlq}"
    check "$(pf test "${alarm}" = OK -o "${alarm}" = INSUFFICIENT_DATA)" "alarm state OK or INSUFFICIENT_DATA" "${alarm}"
    check "$(pf all_ready "${ready}")" "pods ready" "${ready:-unknown}"
    landing_check
  fi
  if [ "${DRY}" = 1 ]; then
    echo "verify ${expect}${verify_label}: dry run, ${VERIFY_TOTAL} checks not evaluated"
  elif [ "${VERIFY_FAILS}" -eq 0 ]; then
    echo "verify ${expect}${verify_label}: PASS (${VERIFY_TOTAL}/${VERIFY_TOTAL})"
  else
    echo "verify ${expect}${verify_label}: FAIL (${VERIFY_FAILS} of ${VERIFY_TOTAL} failed)"
    exit 1
  fi
}

cmd_simulate() {
  local count=${COUNT:-1}
  while [ $# -gt 0 ]; do
    case "$1" in
      --count) count="${2:-}"; shift 2 ;;
      --count=*) count="${1#--count=}"; shift ;;
      COUNT=*) count="${1#COUNT=}"; shift ;;
      *) die "usage: cw.sh simulate [--count N]" ;;
    esac
  done
  [[ "${count}" =~ ^[1-9][0-9]*$ ]] || die "count must be a positive integer"
  simulate "${count}"
}

utc_minutes_from_now() {
  date -u -d "$1 minutes" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v"$1"M +%Y-%m-%dT%H:%M:%SZ
}

cmd_quiet() {
  require_operator
  local minutes=${1:-${MINUTES:-10}}
  minutes="${minutes#MINUTES=}"
  [[ "${minutes}" =~ ^[0-9]+$ ]] || die "usage: cw.sh quiet [MINUTES]"
  run aws cloudwatch disable-alarm-actions --alarm-names "$(out alarm_name)"
  run aws events disable-rule --name "$(out eventbridge_rule_name)"
  local until; until="$(utc_minutes_from_now "+${minutes}")"
  state_set quiet_until "${until}"
  log "alarm actions and the EventBridge rule are disabled until ${until}; arm or disarm turns them back on"
}

wait_alarm_settled() {  # $1 = purge time; true once a DLQ datapoint after it reads 0 and the alarm is not ALARM
  [ "${DRY}" = 1 ] && return 0
  local since=$1 waited=0 limit=$((SETTLE_SECONDS * 3)) latest
  log "waiting up to ${limit}s for a DLQ datapoint after ${since} before the rule goes back on"
  while [ "${waited}" -lt "${limit}" ]; do
    latest="$(aws cloudwatch get-metric-statistics --namespace AWS/SQS --metric-name ApproximateNumberOfMessagesVisible \
      --dimensions "Name=QueueName,Value=${DLQ}" --statistics Sum --period 60 \
      --start-time "${since}" --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --output json 2>/dev/null \
      | jq -r '.Datapoints | sort_by(.Timestamp) | last | .Sum // empty' 2>/dev/null || true)"
    if [ -n "${latest}" ] && [ "${latest%.*}" = 0 ] && [ "$(alarm_state)" != ALARM ]; then return 0; fi
    sleep 15; waited=$((waited + 15))
  done
  return 1
}

cmd_disarm() {
  require_operator
  cmd_quiet 10
  if namespace_exists; then cmd_apply; else log "namespace ${NS} not found; skipping apply"; fi
  local purged_at; purged_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  run aws sqs purge-queue --queue-url "$(out sqs_queue_url)" || log "purge of ${QUEUE} refused (purged within 60s)"
  run aws sqs purge-queue --queue-url "$(out sqs_dlq_url)" || log "purge of ${DLQ} refused (purged within 60s)"
  run aws cloudwatch set-alarm-state --alarm-name "$(out alarm_name)" --state-value OK --state-reason "cw.sh disarm"
  wait_queues_empty
  run aws cloudwatch enable-alarm-actions --alarm-names "$(out alarm_name)"
  # The forced OK flips back to ALARM when CloudWatch re-evaluates the last full DLQ minute, which would page.
  if [ "${PAGE}" != 0 ] && ! wait_alarm_settled "${purged_at}"; then
    log "alarm $(alarm_state); leaving rule $(out eventbridge_rule_name) $(rule_state). Enable it after make cw-verify EXPECT=after passes"
  else
    enable_rule
  fi
  state_del armed_at
  state_del armed_fault
  state_del quiet_until
  log "disarmed"
}

epoch_of() { date -u -d "$1" +%s 2>/dev/null || date -u -j -f %Y-%m-%dT%H:%M:%SZ "$1" +%s; }

in_reset_scope() {  # run branch or tenant name, minus its demo-/otterworks- prefix
  local name=$1 since=$2 ts
  case "${name}" in cw-release-*) return 1 ;; esac
  [ -z "${since}" ] && return 0
  ts="${name#cw-}"; ts="${ts%%-*}"
  [[ "${ts}" =~ ^[0-9]+$ ]] && [ "${ts}" -ge "${since}" ]
}

cmd_reset() {
  local scope=all
  while [ $# -gt 0 ]; do
    case "$1" in
      --scope) scope="${2:-}"; shift 2 ;;
      --scope=*|SCOPE=*) scope="${1#*=}"; shift ;;
      *) die "usage: cw.sh reset [--scope all|run]" ;;
    esac
  done
  case "${scope}" in all|run) ;; *) die "usage: cw.sh reset [--scope all|run]" ;; esac
  require_operator
  local since=""
  if [ "${scope}" = run ]; then
    local armed; armed="$(state_get armed_at)"
    [ -n "${armed}" ] || die "--scope run needs armed_at in ${STATE_FILE#"${REPO}/"}; run a full reset instead"
    since="$(epoch_of "${armed}")"
    log "scope run: only demo-cw-<ts>-* branches and cw-<ts>-* tenants with ts >= ${since} (${armed})"
  fi
  cmd_disarm
  local branches b candidates
  candidates="$(read_cmd git -C "${REPO}" ls-remote --heads origin 'refs/heads/demo-cw-*' | awk '{sub("refs/heads/", "", $2); print $2}')"
  branches=""
  for b in ${candidates}; do
    if in_reset_scope "${b#demo-}" "${since}"; then branches="${branches} ${b}"; else log "keeping branch ${b}"; fi
  done
  if command -v gh >/dev/null 2>&1; then
    local prs n head
    prs="$(read_cmd gh pr list --repo "${GH_REPO}" --state open --limit 200 --json number,headRefName \
      --jq '.[] | select(.headRefName | startswith("demo-cw-")) | "\(.number) \(.headRefName)"' || true)"
    while read -r n head; do
      [ -n "${n}" ] || continue
      in_reset_scope "${head#demo-}" "${since}" || continue
      run gh pr close "${n}" --repo "${GH_REPO}" --comment "Closed by cloudworker reset."
    done <<<"${prs}"
  else
    log "gh not found; close the open PRs at these links by hand:"
    for b in ${branches}; do log "  https://github.com/${GH_REPO}/pulls?q=is%3Apr+is%3Aopen+head%3A${b}"; done
  fi
  for b in ${branches}; do run git -C "${REPO}" push origin --delete "${b}"; done
  local nss ns
  nss="$(read_cmd kubectl get namespaces -o jsonpath='{.items[*].metadata.name}' || true)"
  for ns in ${nss}; do
    case "${ns}" in
      otterworks-cw-release-*) [ -z "${since}" ] && run "${REPO}/scripts/teardown-tenant.sh" "${ns#otterworks-}" ;;
      otterworks-cw-*)
        if in_reset_scope "${ns#otterworks-}" "${since}"; then
          run "${REPO}/scripts/teardown-tenant.sh" "${ns#otterworks-}"
        else
          log "keeping tenant ${ns#otterworks-}"
        fi ;;
    esac
  done
  run aws sqs set-queue-attributes --queue-url "$(out sqs_queue_url)" \
    --attributes "MessageRetentionPeriod=${DRIFT_RETENTION}"
  state_del quiet_until
  log "reset complete"
}

cmd_teardown() {
  require_operator
  local observer builder user
  observer="$(out devin_observer_role_arn)"
  builder="$(out devin_builder_role_arn)"
  user="$(out devin_reader_user_name)"
  cmd_reset
  run bash "${AWS_AUTH}" remove "${observer}" "${builder}"
  run kubectl delete -f "${RBAC}" --ignore-not-found
  delete_reader_keys "${user}"
  run rm -f "${READER_FILE}"
  state_del baseline_image
  if [ "${TEARDOWN_TENANT:-false}" = true ]; then
    dns_filters remove
    run "${REPO}/scripts/teardown-tenant.sh" "${TENANT}"
  else
    log "leaving tenant ${TENANT} in place (TEARDOWN_TENANT=true removes it)"
  fi
  webhook_env
  run terraform -chdir="${TF_DIR}" init -input=false
  run terraform -chdir="${TF_DIR}" destroy -input=false -auto-approve
  run rm -f "${OUTPUTS}"
  log "teardown complete"
}

cmd_trail() {
  local start; start="$(utc_minutes_from_now -120)"
  local events
  local -a args=(aws cloudtrail lookup-events --region "${AWS_REGION}" --start-time "${start}" --output json)
  if [ -n "${CW_TRAIL_MAX:-}" ]; then args+=(--max-items "${CW_TRAIL_MAX}"); fi
  events="$(read_cmd "${args[@]}")"
  [ -n "${events}" ] || return 0
  if [ -n "${CW_TRAIL_MAX:-}" ] && jq -e '.NextToken != null' >/dev/null 2>&1 <<<"${events}"; then
    log "warning: CloudTrail results are truncated at CW_TRAIL_MAX=${CW_TRAIL_MAX} events"
  fi
  {
    printf 'TIME\tUSER\tEVENT\tSOURCE\n'
    jq -r '.Events[] | (.CloudTrailEvent | fromjson) as $e
      | ($e.userIdentity.sessionContext.sessionIssuer.userName // $e.userIdentity.userName // "") as $who
      | select($who | startswith("devin-cw-"))
      | [.EventTime, (if $e.userIdentity.type == "AssumedRole" then "\($who)/\(.Username // "")" else $who end), .EventName, .EventSource]
      | @tsv' <<<"${events}"
  } | column -t -s $'\t'
}

if [ "${DRY}" = 1 ]; then
  log "dry run: commands are printed, not run"
  [ -s "${OUTPUTS}" ] || show terraform -chdir="${TF_DIR}" output -raw '<name>'
fi
verb="${1:-}"
[ $# -gt 0 ] && shift
case "${verb}" in
  up) cmd_up ;;
  apply) cmd_apply ;;
  credentials) cmd_credentials ;;
  arm) cmd_arm "$@" ;;
  status) cmd_status "$@" ;;
  verify) cmd_verify "$@" ;;
  simulate) cmd_simulate "$@" ;;
  quiet) cmd_quiet "$@" ;;
  disarm) cmd_disarm ;;
  reset) cmd_reset "$@" ;;
  teardown) cmd_teardown ;;
  trail) cmd_trail ;;
  -h|--help|help|"") usage ;;
  *) usage; die "unknown verb: ${verb}" ;;
esac
