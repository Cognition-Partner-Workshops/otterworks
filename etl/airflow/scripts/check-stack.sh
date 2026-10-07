#!/usr/bin/env bash
# Fail unless the local Airflow webserver and scheduler report healthy, every DAG file in
# the image has been parsed, and the UI lists zero import errors.
set -euo pipefail

BASE_URL="${AIRFLOW_URL:-http://localhost:${AIRFLOW_WEB_PORT:-8280}}"
AUTH="${AIRFLOW_ADMIN_USER:-airflow}:${AIRFLOW_ADMIN_PASSWORD:-airflow}"
EXPECTED_DAG="${EXPECTED_DAG:-otterworks_platform_check}"
TIMEOUT="${CHECK_TIMEOUT:-180}"

api() { curl -fsS -u "$AUTH" "$BASE_URL$1"; }
field() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

deadline=$((SECONDS + TIMEOUT))
until api "/api/v1/dags/$EXPECTED_DAG" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "FAIL: DAG $EXPECTED_DAG not parsed within ${TIMEOUT}s" >&2
    exit 1
  fi
  sleep 5
done

health="$(curl -fsS "$BASE_URL/health")"
meta="$(field "d['metadatabase']['status']" <<<"$health")"
sched="$(field "d['scheduler']['status']" <<<"$health")"
dags="$(api "/api/v1/dags?limit=100" | field "' '.join(sorted(x['dag_id'] for x in d['dags']))")"
errors="$(api "/api/v1/importErrors")"
error_count="$(field "d['total_entries']" <<<"$errors")"

echo "webserver /health: metadatabase=$meta scheduler=$sched"
echo "dags: $dags"
echo "import errors: $error_count"

if [[ "$meta" != healthy || "$sched" != healthy ]]; then
  echo "FAIL: Airflow reports unhealthy components" >&2
  exit 1
fi
if [[ "$error_count" != 0 ]]; then
  field "'\n'.join(f\"{e['filename']}: {e['stack_trace']}\" for e in d['import_errors'])" <<<"$errors" >&2
  echo "FAIL: $error_count DAG import error(s)" >&2
  exit 1
fi
echo "OK"
