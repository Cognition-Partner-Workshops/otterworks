#!/usr/bin/env bash
# Harness for the legacy-portal-serverless demo: Terraform root, replay, reset and teardown per run token,
# plus the Java deploys through CodeDeploy, the bad-build drill and the page status.
#   scripts/lp-serverless.sh up|replay|status|reset|down|verify-clean|deploy|break|heal|page-status
# Inputs come from the environment: RUN (lp-<yyyymmdd>-<two letters or digits>), CTX, STAGE, EXPIRES_DAYS,
# MVN_FLAGS (extra Maven arguments for deploy), SKIP_BUILD=1 (deploy the jars already in target/).
# Every command writes a transcript to .demo/legacy-portal/<token>/<command>-<UTC time>.log with the
# AWS account number replaced by <account>.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_ROOT="${ROOT}/infrastructure/terraform/legacy-portal-serverless"
PARITY="${ROOT}/services/legacy-portal/parity"
LAMBDA_SRC="${ROOT}/services/legacy-portal-lambda"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
export AWS_PAGER="" TF_IN_AUTOMATION=1
CMD="${1:-}"; shift || true

die() { echo "lp-serverless: $*" >&2; exit 2; }
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

need_run() {
  [ -n "${RUN:-}" ] || die "RUN is required, e.g. make lp-${CMD} RUN=lp-$(date -u +%Y%m%d)-rh"
  [[ "$RUN" =~ ^lp-[0-9]{8}-[a-z0-9]{2}$ ]] || die "RUN must look like lp-20261005-rh, got ${RUN}"
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

# Same loader as cloudworker/cw.sh webhook_env, with the org secrets first: LP_WEBHOOK_URL
# and LP_WEBHOOK_SECRET when both are set, else the file. Neither value is ever printed.
webhook_env() {
  local file="${LP_WEBHOOK_FILE:-${HOME}/.lp-webhook.json}"
  if [ -n "${LP_WEBHOOK_URL:-}" ] && [ -n "${LP_WEBHOOK_SECRET:-}" ]; then
    TF_VAR_devin_webhook_url="$LP_WEBHOOK_URL"
    TF_VAR_devin_webhook_secret="$LP_WEBHOOK_SECRET"
    export TF_VAR_devin_webhook_url TF_VAR_devin_webhook_secret
    echo "webhook url and secret from LP_WEBHOOK_URL and LP_WEBHOOK_SECRET"
  elif [ -f "$file" ]; then
    TF_VAR_devin_webhook_url="$(jq -r '.url // empty' "$file")"
    TF_VAR_devin_webhook_secret="$(jq -r '.secret // empty' "$file")"
    if [ -z "$TF_VAR_devin_webhook_url" ] || [ -z "$TF_VAR_devin_webhook_secret" ]; then
      die "${file} needs both url and secret"
    fi
    export TF_VAR_devin_webhook_url TF_VAR_devin_webhook_secret
    echo "webhook url and secret from ${file}"
  else
    echo "no LP_WEBHOOK_URL/LP_WEBHOOK_SECRET and no ${file}; the page rule stays disabled"
  fi
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
  tf_init; tf_vars; webhook_env
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
  # Synthetics creates its own function, layer and log group named cwsyn-<canary>-<id>; delete any it left.
  local fn lg layer v
  for fn in $(aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'cwsyn-${RUN}-')].FunctionName" --output text); do
    aws lambda delete-function --function-name "$fn" && echo "deleted Synthetics function ${fn}"
  done
  for layer in $(aws lambda list-layers --query "Layers[?starts_with(LayerName, 'cwsyn-${RUN}-')].LayerName" --output text); do
    for v in $(aws lambda list-layer-versions --layer-name "$layer" --query 'LayerVersions[].Version' --output text); do
      aws lambda delete-layer-version --layer-name "$layer" --version-number "$v" && echo "deleted Synthetics layer ${layer}:${v}"
    done
  done
  for lg in $(aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/cwsyn-${RUN}-" --query 'logGroups[].logGroupName' --output text); do
    aws logs delete-log-group --log-group-name "$lg" && echo "deleted Synthetics log group ${lg}"
  done
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
  check_gone aws secretsmanager describe-secret --secret-id "${RUN}/aurora/master"  # runs applied before RDS managed the master secret
  # RDS deletes the secret it manages with the cluster; it carries the cluster ARN in its tags, not the run token.
  n="$(aws secretsmanager list-secrets --filters Key=owning-service,Values=rds \
    --query "length(SecretList[?Tags[?ends_with(Value, ':cluster:${RUN}')]])" --output text)"
  echo "  RDS-managed secrets of cluster ${RUN}: ${n}"; [ "$n" = 0 ] || left=1
  for role in consumer codedeploy probe eventbridge-invoke; do check_gone aws iam get-role --role-name "${RUN}-${role}"; done
  check_gone aws lambda get-function --function-name "${RUN}-notifications"
  check_gone aws events describe-event-bus --name "otterworks-${RUN}"
  check_gone aws dynamodb describe-table --table-name "otterworks-${RUN}-notifications"
  check_gone aws deploy get-application --application-name "$RUN"
  check_gone aws synthetics get-canary --name "${RUN}-probe"
  check_gone aws s3api head-bucket --bucket "${RUN}-probe-artifacts-${account}"
  check_gone aws events describe-rule --name "${RUN}-page-devin"
  check_gone aws events describe-connection --name "${RUN}-devin-webhook"
  check_gone aws events describe-api-destination --name "${RUN}-devin-webhook"
  check_gone aws sqs get-queue-url --queue-name "${RUN}-page-dlq"
  n="$(aws cloudwatch describe-alarms --alarm-name-prefix "$RUN" --alarm-types MetricAlarm CompositeAlarm --query 'length([MetricAlarms, CompositeAlarms][])' --output text)"
  echo "  alarms named ${RUN}*: ${n}"; [ "$n" = 0 ] || left=1
  n="$(aws lambda list-functions --query "length(Functions[?starts_with(FunctionName, 'cwsyn-${RUN}-')])" --output text)"
  echo "  Synthetics functions cwsyn-${RUN}-*: ${n}"; [ "$n" = 0 ] || left=1
  n="$(aws logs describe-log-groups --log-group-name-pattern "$RUN" --query 'length(logGroups)' --output text)"
  echo "  log groups matching ${RUN}: ${n}"; [ "$n" = 0 ] || left=1
  if [ "$left" = 0 ]; then echo "CLEAN: nothing tagged or named ${RUN} remains"; else echo "NOT CLEAN"; return 1; fi
}

# --- Java deploys, the bad-build drill and the page --------------------------------------------------

declare -A HANDLERS=(
  [announcements]=com.otterworks.legacyportal.lambda.AnnouncementsHandler::handleRequest
  [preferences]=com.otterworks.legacyportal.lambda.preferences.PreferencesHandler::handleRequest
  [feedback]=com.otterworks.legacyportal.lambda.feedback.FeedbackHandler::handleRequest
)
declare -A READ_PATHS=(
  [announcements]=/api/announcements
  [preferences]=/api/preferences/lp-drill
  [feedback]="/api/feedback?userId=lp-drill"
)
JAVA_MEMORY_MB="${JAVA_MEMORY_MB:-1024}"
BOOTSTRAP_CONFIG=CodeDeployDefault.LambdaAllAtOnce

contexts() {
  case "${CTX:-all}" in
    all) echo announcements preferences feedback ;;
    announcements|preferences|feedback) echo "$CTX" ;;
    *) die "CTX must be announcements, preferences, feedback or all" ;;
  esac
}

one_context() {
  case "${CTX:-}" in
    announcements|preferences|feedback) ;;
    *) die "CTX must be one of announcements, preferences, feedback, e.g. make lp-${CMD} RUN=${RUN} CTX=announcements" ;;
  esac
}

out() { jq -r --arg k "$1" '.[$k].value' <<<"$OUTPUTS_JSON"; }

live_version() { aws lambda get-alias --function-name "${RUN}-${1}" --name live --query FunctionVersion --output text; }

version_runtime() { aws lambda get-function-configuration --function-name "${RUN}-${1}" --qualifier "$2" --query Runtime --output text; }

# Sets FAIL_READS on $LATEST (keeping every other variable), applies the Java runtime and handler,
# and publishes a version. Prints the version number.
publish_config() {
  local ctx="$1" fail="$2" fn="${RUN}-${1}" env
  env="$(aws lambda get-function-configuration --function-name "$fn" --query 'Environment.Variables' --output json \
    | jq -c --arg f "$fail" '{Variables: ((. // {}) + {FAIL_READS: $f})}')"
  aws lambda update-function-configuration --function-name "$fn" --runtime java21 \
    --handler "${HANDLERS[$ctx]}" --memory-size "$JAVA_MEMORY_MB" --environment "$env" >/dev/null
  aws lambda wait function-updated-v2 --function-name "$fn"
  aws lambda publish-version --function-name "$fn" \
    --description "FAIL_READS=${fail} $(git -C "$ROOT" rev-parse --short HEAD) $(now)" --query Version --output text
}

upload_jar() {
  local ctx="$1" fn="${RUN}-${1}" jar
  if [ "${SKIP_BUILD:-0}" != 1 ]; then
    # shellcheck disable=SC2086
    (cd "${LAMBDA_SRC}/${ctx}" && mvn -q -B ${MVN_FLAGS:-} package) >&2
  fi
  jar="$(find "${LAMBDA_SRC}/${ctx}/target" -maxdepth 1 -name '*.jar' ! -name 'original-*' | head -1)"
  [ -n "$jar" ] || die "no jar in ${LAMBDA_SRC}/${ctx}/target"
  aws lambda update-function-code --function-name "$fn" --zip-file "fileb://${jar}" >/dev/null
  aws lambda wait function-updated-v2 --function-name "$fn"
  echo "  ${ctx}: uploaded ${jar#"${ROOT}"/} ($(du -h "$jar" | cut -f1))" >&2
}

# create_deployment <ctx> <target version> <config> <alarms on|off> <description>; prints the deployment id.
create_deployment() {
  local ctx="$1" target="$2" config="$3" alarms="$4" desc="$5" fn="${RUN}-${1}" current appspec input
  current="$(live_version "$ctx")"
  appspec="$(printf '{"version":0.0,"Resources":[{"live":{"Type":"AWS::Lambda::Function","Properties":{"Name":"%s","Alias":"live","CurrentVersion":"%s","TargetVersion":"%s"}}}]}' \
    "$fn" "$current" "$target")"
  input="$(jq -nc --arg app "$(out codedeploy_app)" --arg grp "$ctx" --arg cfg "$config" --arg spec "$appspec" --arg desc "$desc" \
    '{applicationName: $app, deploymentGroupName: $grp, deploymentConfigName: $cfg, description: $desc,
      revision: {revisionType: "AppSpecContent", appSpecContent: {content: $spec}}}')"
  if [ "$alarms" = off ]; then
    input="$(jq -c --arg a "$(out alarm_5xx_rate)" --arg b "$(out alarm_lambda_errors)" \
      '. + {overrideAlarmConfiguration: {enabled: false, ignorePollAlarmFailure: false, alarms: [{name: $a}, {name: $b}]}}' <<<"$input")"
  fi
  echo "  ${ctx}: live ${current} -> ${target}, ${config}, alarm rollback ${alarms}" >&2
  aws deploy create-deployment --cli-input-json "$input" --query deploymentId --output text
}

deployment_line() {
  aws deploy get-deployment --deployment-id "$1" --output json | jq -r '.deploymentInfo |
    "\(.deploymentId) \(.deploymentGroupName) \(.status) \(.deploymentConfigName)"
    + (if .rollbackInfo.rollbackDeploymentId then " rollback=\(.rollbackInfo.rollbackDeploymentId)" else "" end)
    + (if .errorInformation then " error=\(.errorInformation.code): \(.errorInformation.message)" else "" end)'
}

deployment_status() { aws deploy get-deployment --deployment-id "$1" --query deploymentInfo.status --output text; }

alarm_state() {
  aws cloudwatch describe-alarms --alarm-names "$1" --alarm-types MetricAlarm CompositeAlarm --output json \
    | jq -r '(.MetricAlarms + .CompositeAlarms)[0].StateValue // "missing"'
}

rate_now() {
  aws cloudwatch get-metric-data --start-time "$(date -u -d '-4 min' +%FT%TZ)" --end-time "$(date -u +%FT%TZ)" --output json \
    --metric-data-queries "$(jq -nc --arg api "$(out api_id)" '[
      {Id: "e", ReturnData: false, MetricStat: {Metric: {Namespace: "AWS/ApiGateway", MetricName: "5xx", Dimensions: [{Name: "ApiId", Value: $api}]}, Period: 60, Stat: "Sum"}},
      {Id: "c", ReturnData: false, MetricStat: {Metric: {Namespace: "AWS/ApiGateway", MetricName: "Count", Dimensions: [{Name: "ApiId", Value: $api}]}, Period: 60, Stat: "Sum"}},
      {Id: "r", Expression: "IF(c > 0, 100 * e / c, 0)", ReturnData: true}]')" \
    | jq -r '.MetricDataResults[0] | [range(0; .Values | length) as $i | "\(.Timestamps[$i][11:16]) \(.Values[$i] | floor)%"] | reverse | join(" ") | if . == "" then "no datapoints yet" else . end'
}

# Light read traffic on one context, so the rate alarm does not depend on the probe alone.
read_traffic() {
  local path="${READ_PATHS[$1]}" codes=""
  for _ in 1 2 3 4; do codes+="$(curl -s -o /dev/null -w '%{http_code}' "${API_URL%/}${path}") "; done
  echo "${codes% }"
}

# watch <ctx> <deployment id or -> <target alarm state> <timeout seconds>
watch_until() {
  local ctx="$1" dep="$2" want="$3" deadline=$(( $(date +%s) + $4 )) dstat="-" page rate5 errs
  while :; do
    [ "$dep" = - ] || dstat="$(deployment_status "$dep")"
    page="$(alarm_state "$(out alarm_page)")"; rate5="$(alarm_state "$(out alarm_5xx_rate)")"; errs="$(alarm_state "$(out alarm_lambda_errors)")"
    printf '%s  deploy=%-10s live=v%-3s GET %s -> %s  5xx-rate=%s lambda-errors=%s page=%s  rate/min: %s\n' \
      "$(date -u +%H:%M:%S)" "$dstat" "$(live_version "$ctx")" "${READ_PATHS[$ctx]%%\?*}" "$(read_traffic "$ctx")" \
      "$rate5" "$errs" "$page" "$(rate_now)"
    case "$dstat" in Failed|Stopped) [ "$want" = Succeeded ] && return 1 ;; esac
    if [ "$want" = Succeeded ] && [ "$dstat" = Succeeded ]; then return 0; fi
    if [ "$want" != Succeeded ] && [ "$page" = "$want" ]; then return 0; fi
    [ "$(date +%s)" -lt "$deadline" ] || { echo "timed out waiting for ${want}"; return 1; }
    sleep 15
  done
}

alarm_summary() {
  aws cloudwatch describe-alarms --alarm-names "$(out alarm_5xx_rate)" "$(out alarm_lambda_errors)" "$(out alarm_page)" \
    --alarm-types MetricAlarm CompositeAlarm --output json \
    | jq -r '(.MetricAlarms + .CompositeAlarms)[] | "  \(.AlarmName) \(.StateValue) since \(.StateUpdatedTimestamp[0:19])Z: \(.StateReason)"'
}

cmd_deploy() {
  need_run; start_transcript "$RUN"
  local t0 ctx v cur config alarms ids=() rc=0; t0="$(date +%s)"
  tf_init >/dev/null; load_outputs
  echo "building and publishing the Java handlers from ${LAMBDA_SRC#"${ROOT}"/} at $(git -C "$ROOT" rev-parse --short HEAD)"
  for ctx in $(contexts); do
    upload_jar "$ctx"
    v="$(publish_config "$ctx" 0)"
    cur="$(live_version "$ctx")"
    if [ "$cur" = "$v" ]; then echo "  ${ctx}: live already on version ${v}"; continue; fi
    # The placeholder answers 501, so moving off it goes all at once and without the 5xx alarm.
    if [ "$(version_runtime "$ctx" "$cur")" = java21 ]; then config="$(out deployment_config)"; alarms=on
    else config="$BOOTSTRAP_CONFIG"; alarms=off; fi
    ids+=("$(create_deployment "$ctx" "$v" "$config" "$alarms" "lp-deploy ${ctx} v${v}")")
  done
  for id in "${ids[@]}"; do
    echo "deployment ${id}"
    while :; do case "$(deployment_status "$id")" in Succeeded|Failed|Stopped) break ;; esac; sleep 15; done
    deployment_line "$id"
    [ "$(deployment_status "$id")" = Succeeded ] || rc=1
  done
  if [ "$rc" = 0 ] && [ "$(aws synthetics get-canary --name "$(out probe_canary)" --query Canary.Status.State --output text)" != RUNNING ]; then
    aws synthetics start-canary --name "$(out probe_canary)"
    echo "started probe $(out probe_canary): GET /api/announcements and GET /api/preferences/synthetic-probe every minute"
  fi
  echo "live aliases:"
  for ctx in announcements preferences feedback; do echo "  ${RUN}-${ctx}:live -> v$(live_version "$ctx") ($(version_runtime "$ctx" "$(live_version "$ctx")"))"; done
  echo "lp-deploy wall clock: $(elapsed "$t0")"
  return "$rc"
}

cmd_break() {
  need_run; one_context; start_transcript "$RUN"
  local t0 v id; t0="$(date +%s)"
  tf_init >/dev/null; load_outputs
  [ "$(version_runtime "$CTX" "$(live_version "$CTX")")" = java21 ] || die "${RUN}-${CTX}:live is not a Java version; run make lp-deploy RUN=${RUN} first"
  echo "bad build: same code as live, FAIL_READS=1 (every GET on ${CTX} answers 500)"
  v="$(publish_config "$CTX" 1)"
  id="$(create_deployment "$CTX" "$v" "$(out deployment_config)" on "lp-break ${CTX} v${v} FAIL_READS=1")"
  echo "CodeDeploy deployment id: ${id}"
  echo "tailing the alarms until $(out alarm_page) is ALARM (each line sends 4 GETs to ${CTX})"
  watch_until "$CTX" "$id" ALARM "${BREAK_WAIT_SECONDS:-1500}"
  echo "deployment: $(deployment_line "$id")"
  echo "alarms:"; alarm_summary
  echo "lp-break wall clock: $(elapsed "$t0")"
}

cmd_heal() {
  need_run; one_context; start_transcript "$RUN"
  local t0 inflight v id; t0="$(date +%s)"
  tf_init >/dev/null; load_outputs
  inflight="$(aws deploy list-deployments --application-name "$(out codedeploy_app)" --deployment-group-name "$CTX" \
    --include-only-statuses Created Queued InProgress Ready --query 'deployments[0]' --output text)"
  if [ -n "$inflight" ] && [ "$inflight" != None ]; then
    echo "stopping in-flight deployment ${inflight} with automatic rollback"
    aws deploy stop-deployment --deployment-id "$inflight" --auto-rollback-enabled --output text
    while :; do case "$(deployment_status "$inflight")" in Succeeded|Failed|Stopped) break ;; esac; sleep 10; done
    echo "deployment: $(deployment_line "$inflight")"
    id="$(aws deploy get-deployment --deployment-id "$inflight" --query deploymentInfo.rollbackInfo.rollbackDeploymentId --output text)"
    [ "$id" = None ] && id=-
  else
    echo "good build: same code, FAIL_READS=0, through CodeDeploy with $(out deployment_config)"
    echo "alarm rollback is off for this deployment: the alarm is already in ALARM from the bad version and would stop it at once"
    v="$(publish_config "$CTX" 0)"
    id="$(create_deployment "$CTX" "$v" "$(out deployment_config)" off "lp-heal ${CTX} v${v} FAIL_READS=0")"
  fi
  echo "CodeDeploy deployment id: ${id}"
  echo "waiting for the deployment, then for $(out alarm_page) to return to OK"
  if [ "$id" != - ]; then watch_until "$CTX" "$id" Succeeded "${HEAL_WAIT_SECONDS:-1500}"; fi
  watch_until "$CTX" - OK "${HEAL_WAIT_SECONDS:-1500}"
  [ "$id" = - ] || echo "deployment: $(deployment_line "$id")"
  echo "alarms:"; alarm_summary
  echo "lp-heal wall clock: $(elapsed "$t0")"
}

cmd_page_status() {
  need_run; start_transcript "$RUN"
  local name rule since ctx
  tf_init >/dev/null; load_outputs
  echo "alarms:"; alarm_summary
  for name in "$(out alarm_page)" "$(out alarm_5xx_rate)" "$(out alarm_lambda_errors)"; do
    echo; echo "alarm history ${name} (state changes, newest first):"
    aws cloudwatch describe-alarm-history --alarm-name "$name" --alarm-types MetricAlarm CompositeAlarm --history-item-type StateUpdate --max-items 10 --output json \
      | jq -r '.AlarmHistoryItems[] | "  \(.Timestamp[0:19])Z \(.HistorySummary)"' | sed '/^$/d'
  done
  echo; echo "deployment history ($(out codedeploy_app), newest first):"
  for ctx in announcements preferences feedback; do
    for id in $(aws deploy list-deployments --application-name "$(out codedeploy_app)" --deployment-group-name "$ctx" \
        --query 'deployments[0:5]' --output text); do
      aws deploy get-deployment --deployment-id "$id" --output json | jq -r '.deploymentInfo |
        "  \(.createTime[0:19]) \(.deploymentId) \(.deploymentGroupName) \(.status) \(.deploymentConfigName) \(.description // "")"
        + (if .rollbackInfo.rollbackDeploymentId then " rollback=\(.rollbackInfo.rollbackDeploymentId)" else "" end)
        + (if .rollbackInfo.rollbackTriggeringDeploymentId then " rolls back \(.rollbackInfo.rollbackTriggeringDeploymentId)" else "" end)'
    done
  done
  rule="$(out page_rule)"
  echo; echo "page rule ${rule} on the default bus: $(aws events describe-rule --name "$rule" --query State --output text)"
  aws events describe-api-destination --name "$(out page_api_destination)" --output json \
    | jq -r '"api destination \(.Name): \(.ApiDestinationState), POST to host \(.InvocationEndpoint | sub("^https://"; "") | split("/")[0])"'
  since="$(date -u -d '-24 hours' +%FT%TZ)"
  echo "last EventBridge invocations of the API destination (rule ${rule}, last 24 h):"
  for name in Invocations FailedInvocations InvocationsSentToDlq; do
    aws cloudwatch get-metric-statistics --namespace AWS/Events --metric-name "$name" --dimensions "Name=RuleName,Value=${rule}" \
      --start-time "$since" --end-time "$(date -u +%FT%TZ)" --period 60 --statistics Sum --output json \
      | jq -r --arg m "$name" '[.Datapoints[] | select(.Sum > 0)] | sort_by(.Timestamp) |
          if length == 0 then "  \($m): none" else "  \($m): \(map(.Sum) | add | floor) in total, last at \(.[-1].Timestamp)" end'
  done
  echo "page DLQ messages: $(aws sqs get-queue-attributes --queue-url "$(out page_dlq_url)" --attribute-names ApproximateNumberOfMessages --query Attributes.ApproximateNumberOfMessages --output text)"
}

case "$CMD" in
  up) cmd_up ;;
  replay) cmd_replay ;;
  status) cmd_status ;;
  reset) cmd_reset ;;
  down) cmd_down ;;
  verify-clean) cmd_verify_clean ;;
  deploy) cmd_deploy ;;
  break) cmd_break ;;
  heal) cmd_heal ;;
  page-status) cmd_page_status ;;
  *) die "usage: lp-serverless.sh up|replay|status|reset|down|verify-clean|deploy|break|heal|page-status (RUN, CTX, STAGE from the environment)" ;;
esac
