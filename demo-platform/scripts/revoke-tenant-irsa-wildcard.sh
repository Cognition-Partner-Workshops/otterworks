#!/usr/bin/env bash
# revoke-tenant-irsa-wildcard.sh — strip tenant access from the shared IRSA roles.
#
# Older platform builds widened every shared per-service role
# (otterworks-<svc>-<env>) to trust system:serviceaccount:otterworks-*:<svc>, plus
# per-tenant exact statements from old deploys. That let any tenant namespace
# (and any namespace matching the glob) assume the shared role and its
# bucket/table-wide data access. Tenants now get their own exact-subject roles
# from scripts/deploy-tenant.sh, so the shared roles must trust only the golden
# namespace again. This rewrites each live trust policy to keep exactly
#   system:serviceaccount:<golden ns>:<svc>     (fluent-bit: <golden ns>-system)
# and drops every other subject and every StringLike sub condition. Terraform's
# modules/irsa produces the same result on the next apply; this closes the gap
# before then.
#
# Usage: ENV=dev [DRY_RUN=false] ./revoke-tenant-irsa-wildcard.sh
# Defaults to DRY_RUN=true (prints the roles it would change). Requires aws, jq,
# and iam:GetRole + iam:UpdateAssumeRolePolicy on the shared roles (an operator
# role; the dashboard role deliberately cannot edit shared role trust).
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
ENVIRONMENT="${ENV:-dev}"
CLUSTER="${EKS_CLUSTER:-otterworks-dev}"
GOLDEN_NS="${GOLDEN_NAMESPACE:-otterworks}"
DRY_RUN="${DRY_RUN:-true}"

SERVICES=(
  api-gateway auth-service file-service document-service search-service
  collab-service notification-service audit-service analytics-service
  admin-service fluent-bit
)

command -v jq >/dev/null || { echo "jq required" >&2; exit 1; }

# <trust doc> <oidc url> <allowed sub> -> trust doc with only the allowed sub.
restrict_trust() {
  jq --arg url "$2" --arg allow "$3" '
    def subs: [ (.Condition.StringEquals[$url+":sub"], .Condition.StringLike[$url+":sub"])
                | select(. != null) | if type=="array" then .[] else . end ];
    .Statement |= map(
      if (subs | length) == 0 then .
      elif (subs | index($allow)) then
        del(.Condition.StringLike[$url+":sub"])
        | (if (.Condition.StringLike // {}) == {} then del(.Condition.StringLike) else . end)
        | .Condition.StringEquals[$url+":sub"] = $allow
      else empty end)' <<<"$1"
}

if [ "${BASH_SOURCE[0]}" != "$0" ]; then return 0; fi

oidc_url="$(aws eks describe-cluster --name "${CLUSTER}" --region "${AWS_REGION}" \
  --query 'cluster.identity.oidc.issuer' --output text 2>/dev/null || echo "")"
oidc_url="${oidc_url#https://}"
[ -n "${oidc_url}" ] || { echo "could not resolve OIDC issuer for ${CLUSTER}" >&2; exit 1; }

for svc in "${SERVICES[@]}"; do
  role="otterworks-${svc}-${ENVIRONMENT}"
  ns="${GOLDEN_NS}"; [ "${svc}" = fluent-bit ] && ns="${GOLDEN_NS}-system"
  doc="$(aws iam get-role --role-name "${role}" \
    --query 'Role.AssumeRolePolicyDocument' --output json 2>/dev/null || echo "")"
  [ -n "${doc}" ] || { echo "skip ${role}: not found"; continue; }
  new="$(restrict_trust "${doc}" "${oidc_url}" "system:serviceaccount:${ns}:${svc}")"
  if [ "$(jq -cS . <<<"${doc}")" = "$(jq -cS . <<<"${new}")" ]; then
    echo "ok   ${role}: already exact-subject only"
  elif [ "$(jq '.Statement | length' <<<"${new}")" = 0 ]; then
    echo "WARN ${role}: no golden-namespace statement to keep; left unchanged" >&2
  elif [ "${DRY_RUN}" = true ]; then
    echo "plan ${role}: would drop non-golden subjects (DRY_RUN=true)"
  else
    aws iam update-assume-role-policy --role-name "${role}" --policy-document "${new}" >/dev/null
    echo "done ${role}: trusts only ${ns}:${svc}"
  fi
done
