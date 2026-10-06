#!/usr/bin/env bash
# Sends each statement of SQL_FILE to the Aurora cluster through the RDS Data API.
# Called by terraform_data.schema; retries while the writer finishes starting or resumes from 0 ACU.
set -euo pipefail
: "${CLUSTER_ARN:?}" "${SECRET_ARN:?}" "${DATABASE:?}" "${SQL_FILE:?}"
export AWS_REGION="${AWS_REGION:-us-east-1}"

run() {
  local sql="$1" attempt out
  for attempt in $(seq 1 30); do
    if out="$(aws rds-data execute-statement --resource-arn "$CLUSTER_ARN" --secret-arn "$SECRET_ARN" \
        --database "$DATABASE" --sql "$sql" --output json 2>&1)"; then
      return 0
    fi
    case "$out" in
      *DatabaseResumingException*|*"is not available"*|*"HttpEndpoint is not enabled"*|*"Communications link failure"*|*StatementTimeoutException*)
        echo "apply-schema: waiting for the cluster (attempt ${attempt}): ${out##*: }" >&2; sleep 10 ;;
      *) echo "$out" >&2; return 1 ;;
    esac
  done
  echo "apply-schema: cluster did not accept statements after 30 attempts" >&2
  return 1
}

n=0
while IFS= read -r stmt; do
  [ -n "$stmt" ] || continue
  run "$stmt"
  n=$((n + 1))
  echo "apply-schema: ${stmt:0:72}"
done < <(grep -v '^--' "$SQL_FILE" | grep -v '^[[:space:]]*$')
echo "apply-schema: ${n} statements applied"
