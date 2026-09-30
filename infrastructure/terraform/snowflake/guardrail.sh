#!/usr/bin/env bash
# IAM guardrail proof for the integration role: assume it the way Snowflake does (sts:ExternalId), then
#   1. list s3://<bucket>/<prefix>          -> allowed (the tenant's own prefix)
#   2. list s3://<bucket>/<other-tenant>/   -> AccessDenied  (default s29-after/)
# The caller must be trusted by the role: apply once with -var 'guardrail_principal_arns=["<caller arn>"]',
# run this, then re-apply without it (README.md "Guardrail proof"). Exits non-zero unless both hold.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OTHER_PREFIX="${1:-s29-after/}"
out() { "${HERE}/tf.sh" output -raw "$1"; }
ROLE_ARN="$(out integration_role_arn)"
EXTERNAL_ID="$(out storage_aws_external_id)"
LOCATION="$(out allowed_location)"                     # s3://<bucket>/<prefix>
BUCKET="$(printf '%s' "${LOCATION#s3://}" | cut -d/ -f1)"
PREFIX="${LOCATION#s3://"${BUCKET}"/}"

creds="$(aws sts assume-role --role-arn "${ROLE_ARN}" --role-session-name ldm-guardrail \
  --external-id "${EXTERNAL_ID}" --query Credentials --output json)"
export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
AWS_ACCESS_KEY_ID="$(jq -r .AccessKeyId <<<"${creds}")"
AWS_SECRET_ACCESS_KEY="$(jq -r .SecretAccessKey <<<"${creds}")"
AWS_SESSION_TOKEN="$(jq -r .SessionToken <<<"${creds}")"
unset AWS_PROFILE
echo "assumed: $(aws sts get-caller-identity --query Arn --output text)"

echo "--- aws s3 ls s3://${BUCKET}/${PREFIX}   (own tenant prefix: expect success)"
aws s3 ls "s3://${BUCKET}/${PREFIX}" >/dev/null && echo "allowed"

echo "--- aws s3 ls s3://${BUCKET}/${OTHER_PREFIX}   (other tenant: expect AccessDenied)"
if err="$(aws s3 ls "s3://${BUCKET}/${OTHER_PREFIX}" 2>&1)"; then
  echo "FAIL: listing ${OTHER_PREFIX} succeeded"; exit 1
fi
echo "${err}"
grep -q AccessDenied <<<"${err}" || { echo "FAIL: expected AccessDenied"; exit 1; }

echo "--- aws s3 ls s3://${BUCKET}/   (bucket root: expect AccessDenied)"
if err="$(aws s3 ls "s3://${BUCKET}/" 2>&1)"; then echo "FAIL: listing the bucket root succeeded"; exit 1; fi
grep -q AccessDenied <<<"${err}" || { echo "FAIL: expected AccessDenied: ${err}"; exit 1; }
echo "AccessDenied"
echo "guardrail: PASS"
