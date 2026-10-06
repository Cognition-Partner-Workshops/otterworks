#!/usr/bin/env bash
# Harness for carving one bounded context out of the legacy portal (strangler fig): the module on API Gateway,
# Lambda and Aurora Serverless v2 (announcements also on EventBridge), every other route still on a
# legacy-portal-ec2 run.
#   scripts/lp-strangler.sh up|deploy|status|reset|replay|events|down|verify-clean
# Inputs come from the environment: RUN (lp-<ann|pref|fb>-<yyyymmdd>-<two characters>; the abbreviation picks
# the module), MODULE (optional, announcements|preferences|feedback, must match RUN), EC2_RUN (the lp-ec2 run
# whose ALB the $default route forwards to; up only, later commands read it from the state), TARGET (replay:
# both|ec2|api), EXPIRES_DAYS. Every command writes a transcript to .demo/legacy-portal/<token>/<command>-<UTC
# time>.log with the AWS account number replaced by <account>.
#
# Resetting and replaying truncate the three context tables on the shared EC2 box, so reset and replay hold a
# lock per EC2 run (an S3 object created with If-None-Match) and parallel runs take turns there.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_ROOT="${ROOT}/infrastructure/terraform/legacy-portal-strangler"
STATE_BUCKET="otterworks-terraform-state"
STATE_PREFIX="otterworks/legacy-portal-strangler"
PARITY="${ROOT}/services/legacy-portal/parity"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
export AWS_PAGER="" TF_IN_AUTOMATION=1
CMD="${1:-}"; shift || true

die() { echo "lp-mod: $*" >&2; exit 2; }
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

need_run() {
  [ -n "${RUN:-}" ] || die "RUN is required, e.g. make lp-mod-${CMD} RUN=lp-pref-$(date -u +%Y%m%d)-a1"
  [[ "$RUN" =~ ^lp-(ann|pref|fb)-[0-9]{8}-[a-z0-9]{2}$ ]] || die "RUN must look like lp-ann-20261006-a1, lp-pref-... or lp-fb-..., got ${RUN}"
  local mod
  case "${BASH_REMATCH[1]}" in ann) mod=announcements ;; pref) mod=preferences ;; fb) mod=feedback ;; esac
  [ -z "${MODULE:-}" ] || [ "$MODULE" = "$mod" ] || die "RUN ${RUN} names module ${mod}, but MODULE=${MODULE}"
  MODULE="$mod"
  LAMBDA_SRC="${ROOT}/services/legacy-portal-lambda/${MODULE}"
  case "$MODULE" in
    announcements) PREFIX=/api/announcements; TABLE=announcements.announcement ;;
    preferences) PREFIX=/api/preferences; TABLE=user_preferences.user_preference ;;
    feedback) PREFIX=/api/feedback; TABLE=feedback.feedback ;;
  esac
}

start_transcript() {
  local dir="${ROOT}/.demo/legacy-portal/${1}"
  mkdir -p "$dir"
  TRANSCRIPT="${dir}/${CMD}-$(date -u +%Y%m%dT%H%M%SZ).log"
  local account
  account="$(aws sts get-caller-identity --query Account --output text)"
  exec > >(sed -u -E "s/${account}/<account>/g" | tee "$TRANSCRIPT") 2>&1
  echo "# lp-mod-${CMD} run=${1} module=${MODULE:-} started $(now)"
  echo "# caller $(aws sts get-caller-identity --query Arn --output text | sed -E 's#:user/.*#:user/<caller>#')"
  trap 'rc=$?; ec2_unlock; echo "# lp-mod-${CMD} finished $(now) exit=${rc}"; echo "# transcript ${TRANSCRIPT#"${ROOT}"/}"' EXIT
}

tf() { TF_DATA_DIR="${ROOT}/.demo/legacy-portal/${RUN}/.terraform" terraform -chdir="$TF_ROOT" "$@"; }

tf_init() {
  tf init -input=false -reconfigure -no-color \
    -backend-config="key=${STATE_PREFIX}/${RUN}/terraform.tfstate" >/dev/null
  echo "terraform init: state ${STATE_PREFIX}/${RUN}/terraform.tfstate"
}

# The EC2 run token is fixed at the first apply; destroy and later plans reuse it.
tf_vars() {
  local dir="${ROOT}/.demo/legacy-portal/${RUN}"
  if [ ! -s "${dir}/expires" ]; then
    # A fresh checkout (the CD workflow) keeps the Expires tag the run already has.
    local tagged
    tagged="$(aws lambda get-function --function-name "${RUN}-${MODULE}" --query Tags.Expires --output text 2>/dev/null || true)"
    if [[ "$tagged" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then echo "$tagged" > "${dir}/expires"
    else date -u -d "+${EXPIRES_DAYS:-2} days" +%Y-%m-%d > "${dir}/expires"; fi
  fi
  if [ -n "${EC2_RUN:-}" ]; then
    [[ "$EC2_RUN" =~ ^lp-ec2-[0-9]{8}-[a-z0-9]{2}$ ]] || die "EC2_RUN must look like lp-ec2-20261006-b1, got ${EC2_RUN}"
    echo "$EC2_RUN" > "${dir}/ec2_run"
  elif [ ! -s "${dir}/ec2_run" ]; then
    local from_state
    from_state="$(tf output -raw ec2_run_token 2>/dev/null || true)"
    [ -n "$from_state" ] || die "EC2_RUN is required on the first up, e.g. EC2_RUN=lp-ec2-20261006-b1"
    echo "$from_state" > "${dir}/ec2_run"
  fi
  TF_VARS=(-var "run_token=${RUN}" -var "module=${MODULE}" -var "ec2_run_token=$(cat "${dir}/ec2_run")"
    -var "expires=$(cat "${dir}/expires")" -var "jar_path=$(jar_path)")
}

elapsed() { awk -v s="$1" -v e="$(date +%s)" 'BEGIN { printf "%d s (%.1f min)", e - s, (e - s) / 60 }'; }

build_jar() {
  local mvn="mvn"
  command -v mvn >/dev/null || die "mvn and a JDK 21 are needed to build ${LAMBDA_SRC#"${ROOT}"/}"
  # Maven Central rate-limits this egress IP (HTTP 429); the Google Cloud Storage mirror carries the same artifacts.
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
  (cd "$LAMBDA_SRC" && "$mvn" -s "$settings" -q -B package)
  ls -l "$(jar_path)"
}

# The shaded jar each module's pom produces (the names differ per module).
jar_path() {
  find "${LAMBDA_SRC}/target" -maxdepth 1 -name '*.jar' ! -name 'original-*' 2>/dev/null | head -1
}

load_outputs() {
  local json
  json="$(tf output -json)"
  [ "$(jq 'length' <<<"$json")" -gt 0 ] || die "no Terraform outputs for ${RUN}; run make lp-mod-up RUN=${RUN} EC2_RUN=<lp-ec2 run> first"
  OUTPUTS_JSON="$json"
  API_URL="$(jq -r .api_url.value <<<"$json")"
  EC2_URL="$(jq -r .ec2_base_url.value <<<"$json")"
  EC2_RUN_TOKEN="$(jq -r .ec2_run_token.value <<<"$json")"
  CLUSTER_ARN="$(jq -r .aurora_cluster_arn.value <<<"$json")"
  SECRET_ARN="$(jq -r .db_secret_arn.value <<<"$json")"
  DB_NAME="$(jq -r .db_name.value <<<"$json")"
}

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

ec2_instance() {
  aws ec2 describe-instances \
    --filters "Name=tag:run_token,Values=${EC2_RUN_TOKEN}" Name=instance-state-name,Values=running \
    --query 'Reservations[].Instances[].InstanceId' --output text
}

# Runs one psql statement on the monolith's local Postgres through SSM Run Command (the box has no SSH).
ec2_psql() {
  local sql="$1" instance cmd status
  instance="$(ec2_instance)"
  [ -n "$instance" ] || die "no running instance tagged run_token=${EC2_RUN_TOKEN}"
  cmd="$(aws ssm send-command --instance-ids "$instance" --document-name AWS-RunShellScript \
    --comment "lp-mod ${RUN} reset" \
    --parameters "$(jq -cn --arg s "$sql" '{commands: ["sudo -u postgres psql -d legacyportal -v ON_ERROR_STOP=1 -Atc " + ($s | @sh)]}')" \
    --query Command.CommandId --output text)"
  for _ in $(seq 1 30); do
    status="$(aws ssm get-command-invocation --command-id "$cmd" --instance-id "$instance" --query Status --output text 2>/dev/null || echo Pending)"
    case "$status" in
      Success) aws ssm get-command-invocation --command-id "$cmd" --instance-id "$instance" --query StandardOutputContent --output text; return 0 ;;
      Failed|Cancelled|TimedOut) aws ssm get-command-invocation --command-id "$cmd" --instance-id "$instance" --query StandardErrorContent --output text >&2; return 1 ;;
    esac
    sleep 2
  done
  die "SSM command ${cmd} on ${instance} did not finish"
}

reset_aurora() {
  data_api "TRUNCATE ${TABLE} RESTART IDENTITY" >/dev/null
  echo "aurora ${RUN}: truncated ${TABLE}, ids restart at 1 ($(data_api "SELECT count(*) FROM ${TABLE}" | jq -r '.records[0][0].longValue') rows)"
}

# Lock per EC2 run around everything that truncates or replays against the shared box. A lock older than
# LOCK_STALE_SECONDS is a crashed holder and is broken.
LOCK_HELD=0
ec2_lock() {
  local key="${STATE_PREFIX}/locks/${EC2_RUN_TOKEN}.lock" deadline out holder modified age
  deadline=$(( $(date +%s) + ${LOCK_WAIT_SECONDS:-2700} ))
  while :; do
    printf '%s %s\n' "$RUN" "$(now)" > "${ROOT}/.demo/legacy-portal/${RUN}/ec2.lock"
    if out="$(aws s3api put-object --bucket "$STATE_BUCKET" --key "$key" \
        --body "${ROOT}/.demo/legacy-portal/${RUN}/ec2.lock" --if-none-match '*' 2>&1)"; then
      LOCK_HELD=1; LOCK_KEY="$key"
      echo "ec2 lock taken: s3://${STATE_BUCKET}/${key}"
      return 0
    fi
    case "$out" in *PreconditionFailed*|*ConditionalRequestConflict*) ;; *) die "ec2 lock: ${out}" ;; esac
    holder="$(aws s3 cp "s3://${STATE_BUCKET}/${key}" - 2>/dev/null || echo unknown)"
    modified="$(aws s3api head-object --bucket "$STATE_BUCKET" --key "$key" --query LastModified --output text 2>/dev/null || true)"
    age=$(( $(date +%s) - $(date -d "${modified:-now}" +%s) ))
    if [ "$age" -gt "${LOCK_STALE_SECONDS:-1800}" ]; then
      echo "ec2 lock: breaking a ${age} s old lock held by ${holder}"
      aws s3api delete-object --bucket "$STATE_BUCKET" --key "$key" >/dev/null
      continue
    fi
    [ "$(date +%s)" -lt "$deadline" ] || die "ec2 lock: still held by ${holder} after ${LOCK_WAIT_SECONDS:-2700} s"
    echo "$(now) ec2 lock held by ${holder} (${age} s), waiting"
    sleep 20
  done
}

ec2_unlock() {
  [ "$LOCK_HELD" = 1 ] || return 0
  aws s3api delete-object --bucket "$STATE_BUCKET" --key "$LOCK_KEY" >/dev/null && echo "ec2 lock released"
  LOCK_HELD=0
}

reset_ec2() {
  ec2_psql "TRUNCATE announcements.announcement, user_preferences.user_preference, feedback.feedback RESTART IDENTITY" >/dev/null
  echo "ec2 ${EC2_RUN_TOKEN}: truncated the three context tables, ids restart at 1 (rows: $(ec2_psql 'SELECT (SELECT count(*) FROM announcements.announcement) || chr(47) || (SELECT count(*) FROM user_preferences.user_preference) || chr(47) || (SELECT count(*) FROM feedback.feedback)' | tr -d '\n') announcements/preferences/feedback)"
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
  echo
  echo "lp-mod-up wall clock: $(elapsed "$t0")"
}

alarm_state() {
  aws cloudwatch describe-alarms --alarm-names "$1" --query 'MetricAlarms[0].StateValue' --output text
}

# Builds the jar and applies the root, which publishes a new version when the code or the configuration
# changed, then has CodeDeploy shift the live alias to it. The canary rolls back by itself when either
# alarm goes to ALARM; the command fails unless the deployment succeeds.
cmd_deploy() {
  need_run; start_transcript "$RUN"
  local t0 fn="${RUN}-${MODULE}" current target appspec input id status
  t0="$(date +%s)"
  build_jar
  tf_init; tf_vars
  tf plan -input=false -no-color "${TF_VARS[@]}" -out="${ROOT}/.demo/legacy-portal/${RUN}/deploy.tfplan"
  tf apply -input=false -no-color -auto-approve "${ROOT}/.demo/legacy-portal/${RUN}/deploy.tfplan"
  load_outputs
  current="$(aws lambda get-alias --function-name "$fn" --name live --query FunctionVersion --output text)"
  target="$(jq -r .lambda_published_version.value <<<"$OUTPUTS_JSON")"
  if [ "$current" = "$target" ]; then
    echo "live already on version ${target}; nothing to deploy"; return 0
  fi
  aws lambda wait published-version-active --function-name "$fn" --qualifier "$target"
  appspec="$(jq -nc --arg fn "$fn" --arg cur "$current" --arg tgt "$target" \
    '{version: 0.0, Resources: [{live: {Type: "AWS::Lambda::Function", Properties: {Name: $fn, Alias: "live", CurrentVersion: $cur, TargetVersion: $tgt}}}]}')"
  input="$(jq -nc --arg app "$(jq -r .codedeploy_app.value <<<"$OUTPUTS_JSON")" --arg grp "$(jq -r .deployment_group.value <<<"$OUTPUTS_JSON")" \
    --arg spec "$appspec" --arg desc "lp-mod-deploy ${MODULE} v${target} $(git -C "$ROOT" rev-parse --short HEAD)" \
    '{applicationName: $app, deploymentGroupName: $grp, description: $desc, revision: {revisionType: "AppSpecContent", appSpecContent: {content: $spec}}}')"
  id="$(aws deploy create-deployment --cli-input-json "$input" --query deploymentId --output text)"
  echo "deployment ${id}: live ${current} -> ${target}, $(jq -r .deployment_config.value <<<"$OUTPUTS_JSON"), rollback on $(jq -r .alarm_5xx_rate.value <<<"$OUTPUTS_JSON") or $(jq -r .alarm_lambda_errors.value <<<"$OUTPUTS_JSON")"
  while :; do
    status="$(aws deploy get-deployment --deployment-id "$id" --query deploymentInfo.status --output text)"
    printf '%s  deploy=%-10s 5xx-rate=%s errors=%s\n' "$(date -u +%H:%M:%S)" "$status" \
      "$(alarm_state "$(jq -r .alarm_5xx_rate.value <<<"$OUTPUTS_JSON")")" "$(alarm_state "$(jq -r .alarm_lambda_errors.value <<<"$OUTPUTS_JSON")")"
    case "$status" in Succeeded|Failed|Stopped) break ;; esac
    sleep 15
  done
  aws deploy get-deployment --deployment-id "$id" --output json | jq -r '.deploymentInfo |
    "\(.deploymentId) \(.status)" + (if .rollbackInfo.rollbackDeploymentId then " rollback=\(.rollbackInfo.rollbackDeploymentId)" else "" end)
    + (if .errorInformation then " error=\(.errorInformation.code): \(.errorInformation.message)" else "" end)'
  echo "live -> v$(aws lambda get-alias --function-name "$fn" --name live --query FunctionVersion --output text)"
  echo "lp-mod-deploy wall clock: $(elapsed "$t0")"
  [ "$status" = Succeeded ]
}

cmd_status() {
  local scope="${RUN:-all-runs}"
  [ -z "${RUN:-}" ] || need_run
  start_transcript "$scope"
  echo "resources tagged demo=legacy-portal-strangler in ${AWS_REGION}, by run_token:"
  aws resourcegroupstaggingapi get-resources --tag-filters Key=demo,Values=legacy-portal-strangler --output json \
    | jq -r '.ResourceTagMappingList[] | [(.Tags[] | select(.Key=="run_token") | .Value), (.ResourceARN | split(":")[2])] | @tsv' \
    | sort | uniq -c | awk '{ printf "  %-20s %-16s %s\n", $2, $3, $1 }'
  [ -n "${RUN:-}" ] || { echo "set RUN=<token> for one run's outputs, function, cluster and rule"; return 0; }
  tf_init >/dev/null
  if [ "$(tf output -json | jq length)" -eq 0 ]; then echo "no Terraform state with outputs for ${RUN}"; return 0; fi
  load_outputs
  echo; echo "outputs:"; tf output -no-color
  echo; echo "function:"
  aws lambda get-function-configuration --function-name "${RUN}-${MODULE}" --qualifier live --output text \
    --query '[FunctionName,Version,Runtime,MemorySize,State,SnapStart.OptimizationStatus]'
  echo "aurora:"
  aws rds describe-db-clusters --db-cluster-identifier "$RUN" --output text \
    --query 'DBClusters[0].[Status,EngineVersion,ServerlessV2ScalingConfiguration.MinCapacity,ServerlessV2ScalingConfiguration.MaxCapacity,HttpEndpointEnabled]'
  if [ "$MODULE" = announcements ]; then
    echo "rule:"
    aws events describe-rule --name "${RUN}-announcement-published" --event-bus-name "otterworks-${RUN}" --output text \
      --query '[Name,State,EventPattern]'
  fi
  echo "routes of the HTTP API (${PREFIX} on Lambda, the rest on EC2 through \$default):"
  local path
  for path in /health /api/announcements /api/preferences/u1 /api/feedback/average-rating; do
    curl -s -o /dev/null -w "  GET %{url_effective} %{http_code} in %{time_total}s\n" "${API_URL%/}${path}" || true
  done
}

cmd_reset() {
  need_run; start_transcript "$RUN"
  tf_init >/dev/null; load_outputs
  reset_aurora
  ec2_lock
  reset_ec2
}

replay_one() {
  local label="$1" base="$2" out="$3" rc=0
  echo; echo "== replay ${label}: ${base}"
  python3 "${PARITY}/replay.py" --base "$base" --context all --stage full --out "$out" || rc=$?
  echo "replay ${label} exit ${rc} (0 all identical, 1 divergences found, 3 corpus checksum mismatch)"
  return "$rc"
}

parity_table() {
  python3 - "$MODULE" "$@" <<'PY'
import json, sys
from pathlib import Path
module = sys.argv[1]
dirs = [(sys.argv[i], Path(sys.argv[i + 1])) for i in range(2, len(sys.argv), 2)]
ctxs = ["common", "announcements", "preferences", "feedback"]
served = {c: "Lambda + Aurora" if c == module else "EC2" for c in ctxs}
head = "| Context | Cases | Served by (new) | " + " | ".join(f"{l} identical" for l, _ in dirs) + " |"
print(head)
print("|" + "---|" * (3 + len(dirs)))
tot = [0] * len(dirs); total = 0
for c in ctxs:
    res = [json.loads((d / f"{c}.json").read_text()) for _, d in dirs]
    n = res[0]["casesInCorpus"]; total += n
    cells = []
    for i, r in enumerate(res):
        tot[i] += r["identical"]
        cells.append(f"{r['identical']}/{r['casesRun']}" + ("" if not r["divergentIds"] else " (" + ", ".join(r["divergentIds"]) + ")"))
    print(f"| {c} | {n} | {served[c]} | " + " | ".join(cells) + " |")
print(f"| **total** | **{total}** | | " + " | ".join(f"**{t}/{total}**" for t in tot) + " |")
PY
}

cmd_replay() {
  need_run; start_transcript "$RUN"
  local target="${TARGET:-both}" stamp out_ec2 out_api rc=0 args=()
  case "$target" in both|ec2|api) ;; *) die "TARGET must be both, ec2 or api" ;; esac
  tf_init >/dev/null; load_outputs
  (cd "$PARITY" && sha256sum -c SHA256SUMS)
  ec2_lock
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out_ec2="${ROOT}/.demo/legacy-portal/${RUN}/replay-ec2-${stamp}"
  out_api="${ROOT}/.demo/legacy-portal/${RUN}/replay-api-${stamp}"
  # The corpus is ordered and stateful: every replay starts from empty tables with ids from 1.
  if [ "$target" != api ]; then
    reset_ec2
    replay_one "EC2 before (${EC2_RUN_TOKEN} ALB)" "$EC2_URL" "$out_ec2" || rc=1
    args+=("EC2 (${EC2_RUN_TOKEN})" "$out_ec2")
  fi
  if [ "$target" != ec2 ]; then
    reset_ec2; reset_aurora
    replay_one "after (${RUN} HTTP API)" "$API_URL" "$out_api" || rc=1
    args+=("API GW (${RUN})" "$out_api")
  fi
  echo; echo "parity against java-reference.json:"; echo
  parity_table "${args[@]}" | tee "${ROOT}/.demo/legacy-portal/${RUN}/parity-${stamp}.md"
  return "$rc"
}

# Creates one announcement through the new front door and shows where the announcement.published event landed.
cmd_events() {
  need_run
  [ "$MODULE" = announcements ] || die "${MODULE} publishes no events; events is for an lp-ann run"
  start_transcript "$RUN"
  tf_init >/dev/null; load_outputs
  local queue log_group start body
  queue="$(jq -r .notifications_queue_url.value <<<"$OUTPUTS_JSON")"
  log_group="$(jq -r .events_log_group.value <<<"$OUTPUTS_JSON")"
  start="$(( $(date +%s) * 1000 ))"
  body="$(jq -cn --arg t "Event check $(now)" '{title: $t, body: "lp-ann events", published: true}')"
  echo "POST ${API_URL%/}/api/announcements"
  curl -s -i -H 'Content-Type: application/json' -d "$body" "${API_URL%/}/api/announcements" | sed -n '1p;/^{/p'
  echo; echo "notifications queue ${queue##*/}:"
  aws sqs receive-message --queue-url "$queue" --wait-time-seconds 10 --max-number-of-messages 1 \
    --query 'Messages[0].Body' --output text | jq -c '{source, "detail-type", detail}'
  echo; echo "audit log group ${log_group}:"
  sleep 5
  aws logs filter-log-events --log-group-name "$log_group" --start-time "$start" \
    --query 'events[].message' --output text | jq -c '{id, source, "detail-type", detail}'
}

cmd_down() {
  need_run; start_transcript "$RUN"
  local t0; t0="$(date +%s)"
  tf_init; tf_vars
  [ -n "$(jar_path)" ] || build_jar
  tf destroy -input=false -no-color -auto-approve "${TF_VARS[@]}"
  echo
  echo "lp-mod-down wall clock: $(elapsed "$t0")"
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
  check_gone() { if "$@" >/dev/null 2>&1; then echo "  still present: ${*: -1}"; left=1; else echo "  absent: ${*: -1}"; fi; }
  echo "direct lookups:"
  check_gone aws iam get-role --role-name "${RUN}-lambda"
  check_gone aws lambda get-function --function-name "${RUN}-${MODULE}"
  check_gone aws rds describe-db-clusters --db-cluster-identifier "$RUN"
  check_gone aws secretsmanager describe-secret --secret-id "${RUN}/aurora/master"
  check_gone aws events describe-event-bus --name "otterworks-${RUN}"
  check_gone aws sqs get-queue-url --queue-name "${RUN}-announcement-published"
  check_gone aws sqs get-queue-url --queue-name "${RUN}-announcement-published-dlq"
  n="$(aws apigatewayv2 get-apis --query "length(Items[?Name=='${RUN}'])" --output text)"
  echo "  HTTP APIs named ${RUN}: ${n}"; [ "$n" = 0 ] || left=1
  n="$(aws logs describe-log-groups --log-group-name-pattern "$RUN" --query 'length(logGroups)' --output text)"
  echo "  log groups matching ${RUN}: ${n}"; [ "$n" = 0 ] || left=1
  n="$(aws logs describe-resource-policies --query "length(resourcePolicies[?policyName=='${RUN}-announcement-published'])" --output text)"
  echo "  log resource policies named ${RUN}-announcement-published: ${n}"; [ "$n" = 0 ] || left=1
  if [ "$left" = 0 ]; then echo "CLEAN: nothing tagged or named ${RUN} remains"; else echo "NOT CLEAN"; return 1; fi
}

case "$CMD" in
  up) cmd_up ;;
  deploy) cmd_deploy ;;
  status) cmd_status ;;
  reset) cmd_reset ;;
  replay) cmd_replay ;;
  events) cmd_events ;;
  down) cmd_down ;;
  verify-clean) cmd_verify_clean ;;
  *) die "usage: lp-strangler.sh up|deploy|status|reset|replay|events|down|verify-clean (RUN, MODULE, EC2_RUN, TARGET from the environment)" ;;
esac
