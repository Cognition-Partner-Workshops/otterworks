#!/usr/bin/env bash
# Apply the run's Snowflake foundation with schemachange.
#   ./apply.sh builder        migrations/ as the run's builder role (bootstrap.sql first)
#   ./apply.sh accountadmin   migrations_accountadmin/ (needs ACCOUNTADMIN)
# Env: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_PRIVATE_KEY_FILE,
#      optional SNOWFLAKE_PRIVATE_KEY_FILE_PWD, SF_PHASE, SF_COMMIT, SESSION_URL, DRY_RUN=1.
set -euo pipefail
cd "$(dirname "$0")"
target="${1:?usage: apply.sh builder|accountadmin}"
: "${SNOWFLAKE_ACCOUNT:?}" "${SNOWFLAKE_USER:?}" "${SNOWFLAKE_ROLE:?}" "${SNOWFLAKE_PRIVATE_KEY_FILE:?}"
export SNOWFLAKE_ACCOUNT SNOWFLAKE_USER SNOWFLAKE_ROLE SNOWFLAKE_PRIVATE_KEY_FILE
# schemachange honours SNOWFLAKE_HOST over the account; a host left over from another account breaks the JWT.
unset SNOWFLAKE_HOST
SF_PHASE="${SF_PHASE:-dev}"
if [[ "$SF_PHASE" != dev && "$SF_PHASE" != runtime ]]; then
  echo "SF_PHASE must be dev or runtime" >&2
  exit 2
fi
SF_COMMIT="${SF_COMMIT:-$(git rev-parse HEAD)}"
export SF_PHASE SF_COMMIT
if [[ "$SF_PHASE" == dev && -z "${SESSION_URL:-}" ]]; then
  SESSION_URL="$(PYTHONPATH=../pipeline python3 -c 'import pipeline; print(pipeline.SESSION_URL)')"
fi
export SESSION_URL

if [[ "$target" == builder && "${PIPELINE:-0}" == 1 ]]; then
  exec uv run --python 3.12 --with schemachange==4.4.0 --with snowflake-connector-python==4.8.1 \
    python apply_pipeline.py
fi

# Object names come only from sf_attribution.py; the migrations reference them as Jinja vars.
vars="$(python3 ../attribution/sf_attribution.py names \
  --workload doc_usage_dashboard --workload doc_search_api --workload churn_model)"
export SCHEMACHANGE_NAMES="$vars"
name() { python3 -c 'import json,os,sys; print(json.loads(os.environ["SCHEMACHANGE_NAMES"])[sys.argv[1]])' "$1"; }
governance_db="$(name governance_db)"
migrations_wh="$(name migrations_wh)"

case "$target" in
  builder) folder=migrations; history="$governance_db.SCHEMACHANGE.CHANGE_HISTORY" ;;
  accountadmin) folder=migrations_accountadmin; history="$governance_db.SCHEMACHANGE.CHANGE_HISTORY_ACCOUNTADMIN" ;;
  *) echo "unknown target $target" >&2; exit 2 ;;
esac

run=(uv run --python 3.12 --with schemachange==4.4.0 --with snowflake-connector-python==4.8.1)
tag="$(PYTHONPATH=../pipeline python3 - "$target" <<'PY'
import json
import os
import sys
from pipeline import attr

phase = os.environ["SF_PHASE"]
tag = {
    "workload": "platform",
    "phase": phase,
    "commit": os.environ["SF_COMMIT"],
    "run_id": os.environ.get("SF_RUN_ID") or attr.make_run_id("platform", phase),
}
if phase == "dev":
    tag["session_url"] = os.environ["SESSION_URL"]
print(json.dumps(tag, separators=(",", ":")))
PY
)"
export SCHEMACHANGE_QUERY_TAG="$tag"
dry_run_args=()
if [[ "${DRY_RUN:-0}" == 1 ]]; then
  dry_run_args+=(--dry-run --autocommit)
fi

if [[ "$target" == builder && "${DRY_RUN:-0}" != 1 ]]; then
  "${run[@]}" python - <<'PY'
import os, pathlib, snowflake.connector
con = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"], role=os.environ["SNOWFLAKE_ROLE"],
    authenticator="SNOWFLAKE_JWT", private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"],
    private_key_file_pwd=os.environ.get("SNOWFLAKE_PRIVATE_KEY_FILE_PWD"), application="Devin_Demo",
    session_parameters={"QUERY_TAG": os.environ["SCHEMACHANGE_QUERY_TAG"]})
import json
sql = pathlib.Path("bootstrap.sql").read_text()
for key, value in json.loads(os.environ["SCHEMACHANGE_NAMES"]).items():
    sql = sql.replace("{{ " + key + " }}", value)
for _ in con.execute_string(sql):
    pass
con.close()
print("bootstrap.sql applied")
PY
fi

"${run[@]}" schemachange deploy \
  --root-folder "$folder" \
  --change-history-table "$history" \
  --create-change-history-table \
  --snowflake-authenticator snowflake_jwt \
  --snowflake-warehouse "$migrations_wh" \
  --vars "$vars" \
  --query-tag "$tag" \
  "${dry_run_args[@]}"
