#!/usr/bin/env bash
# terraform for this root with the per-token S3 backend next to demo-aws and the PAT kept in the environment.
#   ./tf.sh [--token s30-after] <terraform args...>      e.g. ./tf.sh plan -out=plan.tfplan
# SNOWFLAKE_PAT is exported as SNOWFLAKE_TOKEN (the provider's variable) for the terraform process only; it is
# never written to tfvars, argv or the state backend config.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../../.." && pwd)"
TOKEN="s30-after"
if [ "${1:-}" = "--token" ]; then TOKEN="$2"; shift 2; fi
: "${SNOWFLAKE_PAT:?SNOWFLAKE_PAT unset (programmatic access token for the Snowflake provider)}"
: "${SNOWFLAKE_USER:?SNOWFLAKE_USER unset (the Snowflake user the PAT belongs to)}"
STATE_BUCKET="${DEMO_STATE_BUCKET:-otterworks-terraform-state}"
STATE_KEY="otterworks/demo/${TOKEN}/snowflake.tfstate"
export TF_DATA_DIR="${DEMO_DIR:-${REPO_ROOT}/.demo}/${TOKEN}/tfdata-snowflake"
mkdir -p "${TF_DATA_DIR}"
tf() { SNOWFLAKE_TOKEN="${SNOWFLAKE_PAT}" terraform -chdir="${HERE}" "$@"; }
if [ ! -f "${TF_DATA_DIR}/terraform.tfstate" ] || ! grep -q "\"${STATE_KEY}\"" "${TF_DATA_DIR}/terraform.tfstate"; then
  tf init -input=false -reconfigure \
    -backend-config="bucket=${STATE_BUCKET}" \
    -backend-config="key=${STATE_KEY}" \
    -backend-config="region=${AWS_REGION:-us-east-1}" >&2
fi
tf "$@"
