#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Regression tests for tenant IRSA isolation.
#
# A tenant namespace must only ever be able to assume a role that trusts its own
# exact service-account subject and reaches only its own S3 prefix and DynamoDB
# tables. The shared otterworks-<svc>-<env> roles must trust nothing but the
# golden namespace -- an otterworks-* glob hands every tenant the shared role's
# bucket/table-wide access. Pure policy rendering; no AWS calls.
# ------------------------------------------------------------------------------
# shellcheck disable=SC2034  # fixture globals read by the sourced library
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok   - $1"; }
nope() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else nope "$1 (expected '$3', got '$2')"; fi; }

# shellcheck source=/dev/null
. "${REPO_ROOT}/scripts/lib/tenant-irsa.sh"
# shellcheck source=/dev/null
. "${SCRIPT_DIR}/revoke-tenant-irsa-wildcard.sh"

URL="oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE"
OIDC_ARN="arn:aws:iam::111122223333:oidc-provider/${URL}"

echo "tenant naming"
check "table name"  "$(tenant_table_name acme otterworks-file-metadata-dev)" "otterworks-t-acme--file-metadata-dev"
check "role name"   "$(tenant_role_name acme file-service)" "ow-acme-file-service"
check "s3 prefix"   "$(tenant_s3_prefix acme)" "tenants/acme/"
# sanitize_id collapses "--", so one tenant's table prefix never prefixes another's.
case "$(tenant_table_name acme-x otterworks-a)" in "$(tenant_table_prefix acme)"*) nope "acme prefix matches acme-x tables" ;; *) ok "tenant table prefixes do not overlap" ;; esac

echo "tenant trust policy"
trust="$(tenant_trust_policy "${OIDC_ARN}" "${URL}" otterworks-acme file-service)"
check "exact sub" "$(jq -r --arg u "${URL}" '.Statement[0].Condition.StringEquals[$u+":sub"]' <<<"${trust}")" "system:serviceaccount:otterworks-acme:file-service"
check "audience pinned" "$(jq -r --arg u "${URL}" '.Statement[0].Condition.StringEquals[$u+":aud"]' <<<"${trust}")" "sts.amazonaws.com"
check "no StringLike" "$(jq '[.. | objects | select(has("StringLike"))] | length' <<<"${trust}")" "0"
check "single statement" "$(jq '.Statement | length' <<<"${trust}")" "1"

echo "tenant data policy"
# Read by tenant_role_policy (sourced), which shellcheck cannot see.
S3_FILE_BUCKET="otterworks-files-dev"; S3_AUDIT_BUCKET="otterworks-audit-archive-dev"
DDB_FILE_META="otterworks-t-acme--file-metadata-dev"; DDB_FOLDERS="otterworks-t-acme--folders-dev"
DDB_VERSIONS="otterworks-t-acme--file-versions-dev"; DDB_SHARES="otterworks-t-acme--file-shares-dev"
DDB_NOTIF="otterworks-t-acme--notifications-dev"; DDB_AUDIT="otterworks-t-acme--audit-events-dev"
for svc in file-service notification-service audit-service; do
  pol="$(tenant_role_policy "${svc}" acme us-east-1 111122223333)"
  check "${svc}: S3 objects only under tenants/acme/" \
    "$(jq '[.Statement[] | select(.Action | any(startswith("s3:")) and (index("s3:ListBucket") | not))
            | .Resource[] | select(test(":::[^/]+/tenants/acme/") | not)] | length' <<<"${pol}")" "0"
  check "${svc}: DynamoDB only on otterworks-t-acme-- tables" \
    "$(jq '[.Statement[] | select(.Action | any(startswith("dynamodb:")))
            | .Resource[] | select(test(":table/otterworks-t-acme--") | not)] | length' <<<"${pol}")" "0"
done
pol="$(tenant_role_policy file-service acme us-east-1 111122223333)"
check "file-service: ListBucket limited to tenant prefix" \
  "$(jq -r '.Statement[] | select(.Sid=="TenantPrefixList") | .Condition.StringLike["s3:prefix"][0]' <<<"${pol}")" "tenants/acme/*"
check "unknown service gets no policy" "$(tenant_role_policy api-gateway acme us-east-1 111122223333)" ""

echo "revoke shared-role wildcard"
legacy="$(jq -n --arg u "${URL}" --arg arn "${OIDC_ARN}" '{Version:"2012-10-17",Statement:[
  {Effect:"Allow",Principal:{Federated:$arn},Action:"sts:AssumeRoleWithWebIdentity",
   Condition:{StringLike:{($u+":sub"):["system:serviceaccount:otterworks:file-service","system:serviceaccount:otterworks-*:file-service"]},
              StringEquals:{($u+":aud"):"sts.amazonaws.com"}}},
  {Effect:"Allow",Principal:{Federated:$arn},Action:"sts:AssumeRoleWithWebIdentity",
   Condition:{StringLike:{($u+":sub"):"system:serviceaccount:otterworks-*:file-service"},StringEquals:{($u+":aud"):"sts.amazonaws.com"}}},
  {Effect:"Allow",Principal:{Federated:$arn},Action:"sts:AssumeRoleWithWebIdentity",
   Condition:{StringEquals:{($u+":sub"):"system:serviceaccount:otterworks-acme:file-service",($u+":aud"):"sts.amazonaws.com"}}}]}')"
fixed="$(restrict_trust "${legacy}" "${URL}" "system:serviceaccount:otterworks:file-service")"
check "one statement left" "$(jq '.Statement | length' <<<"${fixed}")" "1"
check "only golden sub" "$(jq -r --arg u "${URL}" '.Statement[0].Condition.StringEquals[$u+":sub"]' <<<"${fixed}")" "system:serviceaccount:otterworks:file-service"
check "audience kept" "$(jq -r --arg u "${URL}" '.Statement[0].Condition.StringEquals[$u+":aud"]' <<<"${fixed}")" "sts.amazonaws.com"
check "no StringLike left" "$(jq '[.. | objects | select(has("StringLike"))] | length' <<<"${fixed}")" "0"
check "idempotent" "$(restrict_trust "${fixed}" "${URL}" "system:serviceaccount:otterworks:file-service" | jq -cS .)" "$(jq -cS . <<<"${fixed}")"

echo "terraform shared-role trust"
irsa_tf="${REPO_ROOT}/infrastructure/terraform/modules/irsa/main.tf"
check "no namespace glob in irsa module" "$(grep -c 'serviceaccount:[^"]*\*' "${irsa_tf}")" "0"
check "sub condition is StringEquals" "$(grep -B2 ':sub"' "${irsa_tf}" | grep -c 'StringLike')" "0"

echo "deploy-tenant never hands tenants the shared roles"
check "IRSA_JSON reset after load_infra_outputs" \
  "$(sed -n '/^load_infra_outputs$/,/^export DDB_NOTIF_PREFS/p' "${REPO_ROOT}/scripts/deploy-tenant.sh" | grep -c '^IRSA_JSON="{}"$')" "1"

echo
echo "${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ]
