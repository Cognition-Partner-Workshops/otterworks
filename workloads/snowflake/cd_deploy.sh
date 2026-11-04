#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
mode=deploy
rollback_commit=""
while (($#)); do
  case "$1" in
    --dry-run) mode=dry-run ;;
    --rollback)
      mode=rollback
      if (($# > 1)) && [[ "$2" != --* ]]; then
        rollback_commit="$2"
        shift
      fi
      ;;
    *) echo "Usage: $0 [--dry-run | --rollback [commit]]" >&2; exit 2 ;;
  esac
  shift
done
export SNOWFLAKE_ACCOUNT="${SFNFR_ACCOUNT:-${SNOWFLAKE_ACCOUNT:-}}"
export SNOWFLAKE_USER="${SFNFR_USER:-${SNOWFLAKE_USER:-}}"
export SNOWFLAKE_ROLE="${SFNFR_ROLE:-${SNOWFLAKE_ROLE:-}}"
unset SNOWFLAKE_HOST
generated_key_files=()
cleanup_generated_keys() {
  for key_file in "${generated_key_files[@]}"; do
    rm -f "$key_file"
  done
}
trap cleanup_generated_keys EXIT
if [[ -n "${SFNFR_PRIVATE_KEY:-}" ]]; then
  : "${RUNNER_TEMP:?RUNNER_TEMP is required to create a temporary builder key file}"
  umask 077
  builder_key_file="$RUNNER_TEMP/snowflake-builder-$$.p8"
  printf '%s' "$SFNFR_PRIVATE_KEY" > "$builder_key_file"
  generated_key_files+=("$builder_key_file")
  export SNOWFLAKE_PRIVATE_KEY_FILE="$builder_key_file"
fi
if [[ -n "${SFNFR_SVC_DOC_USAGE_PRIVATE_KEY:-}" ]]; then
  : "${RUNNER_TEMP:?RUNNER_TEMP is required to create a temporary service key file}"
  umask 077
  service_key_file="$RUNNER_TEMP/snowflake-service-$$.p8"
  printf '%s' "$SFNFR_SVC_DOC_USAGE_PRIVATE_KEY" > "$service_key_file"
  generated_key_files+=("$service_key_file")
  export SNOWFLAKE_SVC_PRIVATE_KEY_FILE="$service_key_file"
fi

cd_py() {
  uv run --python 3.12 \
    --with pyyaml==6.0.2 \
    --with jsonschema==4.23.0 \
    --with snowflake-connector-python==4.8.1 \
    python workloads/snowflake/cd.py "$@"
}
runner_py() {
  uv run --python 3.12 \
    --with pyyaml==6.0.2 \
    --with snowflake-connector-python==4.8.1 \
    python "$@"
}
dbt_py() {
  uv run --python 3.12 --with dbt-snowflake==1.9.4 python workloads/dbt/run.py "$@"
}

if [[ "$mode" == dry-run ]]; then
  export SF_PHASE=runtime
  cd_py plan --results-dir "${SF_CD_RESULTS_DIR:-${RUNNER_TEMP:-/home/ubuntu/notes/cd-logs}/snowflake-cd}"
  exit $?
fi

: "${SNOWFLAKE_ACCOUNT:?SNOWFLAKE_ACCOUNT is required}"
: "${SNOWFLAKE_USER:?SNOWFLAKE_USER is required}"
: "${SNOWFLAKE_ROLE:?SNOWFLAKE_ROLE is required}"
: "${SNOWFLAKE_PRIVATE_KEY_FILE:?SNOWFLAKE_PRIVATE_KEY_FILE is required}"

trigger_commit="${SF_COMMIT:-$(git rev-parse HEAD)}"
if [[ "$mode" == rollback ]]; then
  if [[ -z "$rollback_commit" ]]; then
    rollback_commit="$(cd_py rollback-target --from "$trigger_commit")"
  fi
  commit="$rollback_commit"
else
  commit="$trigger_commit"
fi
export SF_PHASE=runtime SF_COMMIT="$commit"
if [[ "$mode" == rollback ]]; then
  : "${SNOWFLAKE_SVC_PRIVATE_KEY_FILE:?SNOWFLAKE_SVC_PRIVATE_KEY_FILE is required for rollback}"
else
  : "${SNOWFLAKE_SVC_PRIVATE_KEY_FILE:?SNOWFLAKE_SVC_PRIVATE_KEY_FILE is required for deploy}"
fi

results_dir="${SF_CD_RESULTS_DIR:-${RUNNER_TEMP:-/home/ubuntu/notes/cd-logs}/snowflake-cd}"
mkdir -p "$results_dir/logs"
run_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export SF_RUN_ID="$(PYTHONPATH=workloads/pipeline python3 -c 'import os; from pipeline import attr; print(attr.make_run_id("platform", os.environ["SF_PHASE"]))')"
for workload in doc_usage_dashboard doc_search_api churn_model; do
  key="SF_RUN_ID_${workload^^}"
  value="$(PYTHONPATH=workloads/pipeline python3 -c 'import os,sys; from pipeline import attr; print(attr.make_run_id(sys.argv[1], os.environ["SF_PHASE"]))' "$workload")"
  export "$key=$value"
done
record="$results_dir/query_ids.json"
cd_py init-record --commit "$commit" --record "$record"
finalize() {
  local status=$?
  trap - EXIT
  if [[ -f "$record" ]]; then
    if cd_py collect --record "$record" --step final_query_history --since "$run_started" \
      > "$results_dir/logs/final_query_history.log" 2>&1; then
      cat "$results_dir/logs/final_query_history.log"
    else
      cat "$results_dir/logs/final_query_history.log" >&2
      echo "Warning: final query-history collection failed" >&2
    fi
    echo "QUERY_RECORD $record"
  fi
  cleanup_generated_keys
  return "$status"
}
trap finalize EXIT

run_logged() {
  local step="$1"
  shift
  local since
  since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "=== $step ==="
  set +e
  "$@" 2>&1 | tee "$results_dir/logs/$step.log"
  local status=${PIPESTATUS[0]}
  set -e
  if ((status != 0)); then
    cd_py collect --record "$record" --step "$step" --since "$since" || true
    return "$status"
  fi
  cd_py collect --record "$record" --step "$step" --since "$since"
}

if [[ "$mode" == deploy ]]; then
  run_logged gate uv run --with ruff==0.9.10 ruff check workloads/attribution
  run_logged attribution_tests uv run \
    --with pyyaml==6.0.2 --with jsonschema==4.23.0 --with pytest==8.3.5 \
    --with snowflake-connector-python==4.8.1 \
    pytest workloads/attribution/tests -q
  run_logged provenance_validation uv run \
    --with pyyaml==6.0.2 --with jsonschema==4.23.0 \
    python workloads/attribution/validate_provenance.py
  mapfile -t related_tests < <(
    find workloads/pipeline workloads/dbt workloads/snowflake workloads/churn_model workloads/doc_search_api \
      -type f -name 'test_*.py' -print 2>/dev/null
  )
  if ((${#related_tests[@]})); then
    run_logged related_tests uv run \
      --with pyyaml==6.0.2 --with jsonschema==4.23.0 --with pytest==8.3.5 \
      --with snowflake-connector-python==4.8.1 \
      pytest "${related_tests[@]}" -q
  fi
  run_logged foundation_migrations env DRY_RUN=0 PIPELINE=0 workloads/snowflake/apply.sh builder
  run_logged pipeline_migrations env DRY_RUN=0 PIPELINE=1 workloads/snowflake/apply.sh builder
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    printf 'reached_dbt=true\n' >> "$GITHUB_OUTPUT"
  fi
  dbt_results="$results_dir/dbt"
  run_logged dbt_build dbt_py --results-dir "$dbt_results"
  cd_py record-dbt-results --commit "$commit" --results "$dbt_results" --record "$record"
  task_dir="$results_dir/task-project"
  task_evidence="$results_dir/task-deploy.json"
  run_logged deploy_task runner_py workloads/snowflake/deploy_usage_task.py \
    --commit "$commit" --directory "$task_dir" --output "$task_evidence" --query-record "$record"
  app_dir="$results_dir/app-project"
  app_evidence="$results_dir/app-deploy.json"
  run_logged deploy_app runner_py workloads/snowflake/deploy_usage_app.py \
    --commit "$commit" --directory "$app_dir" --output "$app_evidence" \
    --account "$SNOWFLAKE_ACCOUNT" --private-key-file "${SNOWFLAKE_SVC_PRIVATE_KEY_FILE:?}" \
    --query-record "$record"
  run_logged provenance_write cd_py provenance \
    --commit "$commit" --mode deploy --results "$dbt_results" --record "$record" --write
else
  : "${SNOWFLAKE_SVC_PRIVATE_KEY_FILE:?SNOWFLAKE_SVC_PRIVATE_KEY_FILE is required for rollback}"
  project_dir="$results_dir/rollback-project/workloads/dbt"
  mkdir -p "$results_dir/rollback-project"
  git archive "$commit" workloads/dbt | tar -x -C "$results_dir/rollback-project"
  dbt_results="$results_dir/rollback-dbt"
  run_logged rollback_dbt_build dbt_py --project-dir "$project_dir" --results-dir "$dbt_results"
  cd_py record-dbt-results --commit "$commit" --results "$dbt_results" --record "$record"
  task_evidence="$results_dir/rollback-task-deploy.json"
  run_logged rollback_task runner_py workloads/snowflake/deploy_usage_task.py \
    --commit "$commit" --directory "$results_dir/rollback-task-project" \
    --output "$task_evidence" --query-record "$record"
  app_evidence="$results_dir/rollback-app-deploy.json"
  run_logged rollback_app runner_py workloads/snowflake/deploy_usage_app.py \
    --commit "$commit" --directory "$results_dir/rollback-app-project" \
    --output "$app_evidence" --account "$SNOWFLAKE_ACCOUNT" \
    --private-key-file "$SNOWFLAKE_SVC_PRIVATE_KEY_FILE" --query-record "$record"
  run_logged rollback_provenance_write cd_py provenance \
    --commit "$commit" --mode rollback --results "$dbt_results" --record "$record" --write
fi

run_logged provenance_validation uv run \
  --with pyyaml==6.0.2 --with jsonschema==4.23.0 \
  python workloads/attribution/validate_provenance.py
