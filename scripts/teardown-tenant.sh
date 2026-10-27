#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# OtterWorks - Per-Tenant Teardown
#
# Deletes an ephemeral tenant created by deploy-tenant.sh:
#   1. (unless --keep-db) drops the per-tenant RDS database otterworks_<ID>
#      via an in-cluster job (the Devin VM has no direct VPC access to RDS)
#   2. deletes the namespace otterworks-<ID> (all Helm releases, Redis, Meili,
#      config/secrets, ingress, quota, netpol) in one shot
#   3. removes the tenant's service-account subs from the shared IRSA role trust
#      policies (reverse of deploy-tenant's ensure_irsa_trust)
#   4. with --token: deletes ECR image tags containing the token, makes sure the
#      tenant's ingress hosts are gone from Route 53, then lists everything that
#      still bears the token and exits non-zero if anything remains
#
# Usage:
#   ./scripts/teardown-tenant.sh <ATTENDEE_ID> [--keep-db] [--keep-trust]
#                                [--token TOKEN] [--host HOST]... [--verify-only]
#
# --verify-only skips steps 1-3 and only runs the token residue check.
#
# Required env: AWS creds (exported). DB_PASSWORD needed only to drop the DB.
# ------------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/tenant-common.sh
source "${SCRIPT_DIR}/lib/tenant-common.sh"

ATTENDEE_ID=""
KEEP_DB=false
KEEP_TRUST=false
TOKEN=""
VERIFY_ONLY=false
TOKEN_HOSTS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --keep-db)    KEEP_DB=true; shift ;;
    --keep-trust) KEEP_TRUST=true; shift ;;
    --token)      TOKEN="${2:?--token needs a value}"; shift 2 ;;
    --host)       TOKEN_HOSTS+=("${2:?--host needs a value}"); shift 2 ;;
    --verify-only) VERIFY_ONLY=true; shift ;;
    -*)           err "Unknown flag: $1"; exit 1 ;;
    *)            if [ -z "${ATTENDEE_ID}" ]; then ATTENDEE_ID="$1"; else err "Unexpected arg: $1"; exit 1; fi; shift ;;
  esac
done
[ -n "${ATTENDEE_ID}" ] || { err "Usage: $0 <ATTENDEE_ID> [--keep-db] [--keep-trust] [--token TOKEN] [--host HOST]... [--verify-only]"; exit 1; }
[ "${VERIFY_ONLY}" = false ] || [ -n "${TOKEN}" ] || { err "--verify-only needs --token"; exit 1; }

require_bins aws kubectl jq
NS="$(tenant_namespace "${ATTENDEE_ID}")"
T_DB_NAME="$(tenant_db_name "${ATTENDEE_ID}")"

# In-cluster (runner Job) use the pod ServiceAccount + RBAC; only build a
# kubeconfig when running standalone (see deploy-tenant.sh for the rationale).
if [ -z "${KUBERNETES_SERVICE_HOST:-}" ]; then
  aws eks update-kubeconfig --name "${EKS_CLUSTER}" --region "${AWS_REGION}" --alias "${EKS_CLUSTER}" >/dev/null 2>&1 || true
fi

# ------------------------------------------------------------------------------
# Token-scoped cleanup and residue check. A token is a run id stamped on every
# resource a run creates: the demo/token label in Kubernetes, the image tag in
# ECR, a run_token/token tag on AWS resources and a token attribute on the
# control-table item. DNS records carry no tags, so the hosts are passed in.
# ------------------------------------------------------------------------------
CONTROL_TABLE="${CONTROL_TABLE:-otterworks-demo-control}"
DNS_WAIT_SECONDS="${DNS_WAIT_SECONDS:-180}"

delete_token_ecr_tags() {
  local token="$1" repo ids
  for repo in $(aws ecr describe-repositories --region "${AWS_REGION}" --query 'repositories[].repositoryName' --output text 2>/dev/null); do
    ids="$(aws ecr list-images --region "${AWS_REGION}" --repository-name "${repo}" --filter tagStatus=TAGGED --output json 2>/dev/null \
      | jq -c --arg t "${token}" '[.imageIds[] | select(.imageTag | contains($t)) | {imageTag}]')"
    [ -n "${ids}" ] && [ "${ids}" != "[]" ] || continue
    aws ecr batch-delete-image --region "${AWS_REGION}" --repository-name "${repo}" --image-ids "${ids}" >/dev/null \
      && log "  ECR: deleted $(echo "${ids}" | jq -r 'map(.imageTag) | join(", ")') from ${repo}" \
      || warn "  ECR: failed to delete token tags from ${repo}"
  done
}

# Hosted zones that could hold a host, longest suffix match first.
zone_for_host() {
  local host="$1"
  aws route53 list-hosted-zones --output json 2>/dev/null | jq -r --arg h "${host}." '
    [.HostedZones[] | select(.Config.PrivateZone | not) | select(($h | endswith("." + .Name)) or $h == .Name)]
    | sort_by(.Name | length) | reverse | .[0].Id // empty' | sed 's#^/hostedzone/##'
}

# Records named after a host, including the external-dns TXT registry entries.
host_records() {
  local zone="$1" host="$2"
  aws route53 list-resource-record-sets --hosted-zone-id "${zone}" --output json 2>/dev/null | jq -c --arg h "${host}." '
    .ResourceRecordSets[] | select(.Name == $h or .Name == ("a-" + $h) or .Name == ("aaaa-" + $h) or .Name == ("cname-" + $h))'
}

delete_host_dns() {
  local host zone waited=0 rec left
  [ "${#TOKEN_HOSTS[@]}" -gt 0 ] || return 0
  log "Waiting up to ${DNS_WAIT_SECONDS}s for external-dns to drop ${TOKEN_HOSTS[*]}..."
  while :; do
    left=0
    for host in "${TOKEN_HOSTS[@]}"; do
      zone="$(zone_for_host "${host}")"; [ -n "${zone}" ] || continue
      [ -z "$(host_records "${zone}" "${host}")" ] || left=$((left + 1))
    done
    [ "${left}" -gt 0 ] && [ "${waited}" -lt "${DNS_WAIT_SECONDS}" ] || break
    sleep 15; waited=$((waited + 15))
  done
  for host in "${TOKEN_HOSTS[@]}"; do
    zone="$(zone_for_host "${host}")"; [ -n "${zone}" ] || continue
    while IFS= read -r rec; do
      [ -n "${rec}" ] || continue
      aws route53 change-resource-record-sets --hosted-zone-id "${zone}" --change-batch \
        "$(jq -n --argjson r "${rec}" '{Changes:[{Action:"DELETE",ResourceRecordSet:$r}]}')" >/dev/null \
        && log "  DNS: deleted $(echo "${rec}" | jq -r '.Type + " " + .Name')" \
        || warn "  DNS: failed to delete $(echo "${rec}" | jq -r '.Type + " " + .Name')"
    done < <(host_records "${zone}" "${host}")
  done
}

delete_token_control_item() {
  local token="$1" item
  item="$(aws dynamodb get-item --table-name "${CONTROL_TABLE}" --region "${AWS_REGION}" \
    --key "$(jq -n --arg pk "TENANT#${ATTENDEE_ID}" '{PK:{S:$pk},SK:{S:"META"}}')" --output json 2>/dev/null || echo '{}')"
  [ "$(echo "${item}" | jq -r '.Item.token.S // empty')" = "${token}" ] || return 0
  aws dynamodb delete-item --table-name "${CONTROL_TABLE}" --region "${AWS_REGION}" \
    --key "$(jq -n --arg pk "TENANT#${ATTENDEE_ID}" '{PK:{S:$pk},SK:{S:"META"}}')" >/dev/null \
    && log "  control table: deleted TENANT#${ATTENDEE_ID}"
}

# Databases on the shared RDS whose name contains any of the given fragments.
# Runs as an in-cluster Job (the VM has no route to RDS). Prints one per line.
list_dbs_matching() {
  [ -n "${DB_PASSWORD:-}" ] && [ -n "${RDS_HOST:-}" ] || { echo "?db-check-skipped(no DB_PASSWORD/RDS_HOST)"; return 0; }
  local frag job secret where="" f
  for f in "$@"; do where="${where:+${where} OR }datname LIKE '%${f}%'"; done
  frag="$(k8s_name_fragment "$(sanitize_id "$1")" | cut -c1-40)"
  job="token-db-list-${frag}"; secret="token-db-admin-${frag}"
  kubectl get ns "${SYSTEM_NAMESPACE}" >/dev/null 2>&1 || kubectl create ns "${SYSTEM_NAMESPACE}" >/dev/null 2>&1 || true
  apply_db_admin_secret "${SYSTEM_NAMESPACE}" "${secret}"
  kubectl -n "${SYSTEM_NAMESPACE}" delete job "${job}" --ignore-not-found >/dev/null 2>&1 || true
  kubectl apply -n "${SYSTEM_NAMESPACE}" -f - >/dev/null <<YAML
apiVersion: batch/v1
kind: Job
metadata:
  name: ${job}
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: psql
          image: postgres:16-alpine
          env:
            - name: PGPASSWORD
              valueFrom: { secretKeyRef: { name: ${secret}, key: PGPASSWORD } }
          command: ["/bin/sh","-c"]
          args:
            - psql "host=${RDS_HOST} port=${RDS_PORT} dbname=otterworks user=${DB_USER} sslmode=prefer connect_timeout=10" -tAc "SELECT datname FROM pg_database WHERE ${where}"
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits: { cpu: 200m, memory: 128Mi }
YAML
  if kubectl -n "${SYSTEM_NAMESPACE}" wait --for=condition=complete "job/${job}" --timeout=90s >/dev/null 2>&1; then
    kubectl -n "${SYSTEM_NAMESPACE}" logs "job/${job}" 2>/dev/null | sed '/^$/d'
  else
    echo "?db-check-failed"
  fi
  kubectl -n "${SYSTEM_NAMESPACE}" delete job "${job}" --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n "${SYSTEM_NAMESPACE}" delete secret "${secret}" --ignore-not-found >/dev/null 2>&1 || true
}

# List everything that still bears the token. Returns the number of findings.
token_residue() {
  local token="$1" found=0 line repo zone host db_frag
  db_frag="$(printf '%s' "${token}" | tr '[:upper:]-' '[:lower:]_')"
  report() { printf '  %-14s %s\n' "$1" "$2"; found=$((found + 1)); }
  log "Resources still bearing token ${token}:"
  while IFS= read -r line; do [ -n "${line}" ] && report namespace "${line}"; done < <(
    kubectl get ns -o json 2>/dev/null | jq -r --arg t "${token}" \
      '.items[] | select((.metadata.labels["demo/token"] // "") == $t or (.metadata.name | contains($t))) | .metadata.name')
  while IFS= read -r line; do [ -n "${line}" ] && report k8s "${line}"; done < <(
    kubectl get deploy,statefulset,svc,ingress,job,cronjob,configmap,secret,pvc,pod -A -l "demo/token=${token}" \
      -o jsonpath='{range .items[*]}{.metadata.namespace}/{.kind}/{.metadata.name}{"\n"}{end}' 2>/dev/null)
  for repo in $(aws ecr describe-repositories --region "${AWS_REGION}" --query 'repositories[].repositoryName' --output text 2>/dev/null); do
    while IFS= read -r line; do [ -n "${line}" ] && report ecr "${repo}:${line}"; done < <(
      aws ecr list-images --region "${AWS_REGION}" --repository-name "${repo}" --filter tagStatus=TAGGED --output json 2>/dev/null \
        | jq -r --arg t "${token}" '.imageIds[].imageTag | select(contains($t))')
  done
  # shellcheck disable=SC2016  # backticks are JMESPath literals
  for zone in $(aws route53 list-hosted-zones --query 'HostedZones[?Config.PrivateZone==`false`].Id' --output text 2>/dev/null | sed 's#/hostedzone/##g'); do
    while IFS= read -r line; do [ -n "${line}" ] && report dns "${line}"; done < <(
      aws route53 list-resource-record-sets --hosted-zone-id "${zone}" --output json 2>/dev/null \
        | jq -r --arg t "${token}" --argjson hosts "$(printf '%s\n' "${TOKEN_HOSTS[@]:-}" | jq -R . | jq -sc 'map(select(length > 0) | . + ".")')" '
          .ResourceRecordSets[] | select((.Name | contains($t)) or (.Name as $n | $hosts | any(. as $h | $n == $h or $n == ("a-" + $h) or $n == ("cname-" + $h))))
          | .Type + " " + .Name')
  done
  while IFS= read -r line; do [ -n "${line}" ] && report aws-tagged "${line}"; done < <(
    for k in run_token token demo-token; do
      aws resourcegroupstaggingapi get-resources --region "${AWS_REGION}" --tag-filters "Key=${k},Values=${token}" \
        --query 'ResourceTagMappingList[].ResourceARN' --output text 2>/dev/null | tr '\t' '\n'
    done | sort -u)
  while IFS= read -r line; do [ -n "${line}" ] && report iam-role "${line}"; done < <(
    aws iam list-roles --query "Roles[?contains(RoleName, '${token}')].RoleName" --output text 2>/dev/null | tr '\t' '\n')
  while IFS= read -r line; do [ -n "${line}" ] && report control-item "${line}"; done < <(
    aws dynamodb scan --table-name "${CONTROL_TABLE}" --region "${AWS_REGION}" \
      --filter-expression "#t = :t OR contains(PK, :t)" --expression-attribute-names '{"#t":"token"}' \
      --expression-attribute-values "$(jq -n --arg t "${token}" '{":t":{S:$t}}')" --output json 2>/dev/null \
      | jq -r '.Items[] | .PK.S + "/" + .SK.S')
  # shellcheck disable=SC2086  # TOKEN_DB_NAMES is a space-separated list
  while IFS= read -r line; do [ -n "${line}" ] && report database "${line}"; done < <(
    list_dbs_matching "${db_frag}" ${TOKEN_DB_NAMES:-})
  if [ "${found}" -eq 0 ]; then
    log "  none. Token ${token} is clean."
  else
    err "${found} resource(s) still bear token ${token}."
  fi
  return "${found}"
}

if [ "${VERIFY_ONLY}" = true ]; then
  [ -n "${DB_PASSWORD:-}" ] && load_infra_outputs
  TOKEN_DB_NAMES="${TOKEN_DB_NAMES:-${T_DB_NAME}}"
  token_residue "${TOKEN}" || exit 1
  exit 0
fi

if [ -n "${TOKEN}" ] && kubectl get ns "${NS}" >/dev/null 2>&1; then
  for h in $(kubectl -n "${NS}" get ingress -o jsonpath='{.items[*].spec.rules[*].host}' 2>/dev/null); do
    TOKEN_HOSTS+=("${h}")
  done
fi

# --- Step 1: delete the namespace (everything in it) FIRST ---
# This stops every application pod so nothing is still holding a connection to
# the per-tenant database when we drop it in step 2 (avoids DROP racing the
# connection-pool reconnects of live pods). The namespace may already be gone
# (e.g. the TTL reaper deleted it) — that's fine, we still drop the DB below.
if ! kubectl get ns "${NS}" >/dev/null 2>&1; then
  warn "Namespace ${NS} not found (already deleted / reaped); still dropping DB + cleaning IRSA trust."
else
  log "Deleting namespace ${NS}..."
  kubectl delete namespace "${NS}" --wait=true --timeout=180s || \
    warn "Namespace deletion timed out; it may still be terminating."
fi

# --- Step 2: drop the per-tenant database (now that no pods are connected) ---
# Runs regardless of whether the namespace still existed: the drop Job executes
# in ${SYSTEM_NAMESPACE}, not the tenant namespace, so it works even after the
# reaper has removed the tenant namespace (the reaper does NOT drop DBs).
if [ "${KEEP_DB}" = false ] && [ -n "${DB_PASSWORD:-}" ]; then
  load_infra_outputs
  if [ -n "${RDS_HOST}" ]; then
    log "Dropping per-tenant database ${T_DB_NAME} (in-cluster job in ${SYSTEM_NAMESPACE})..."
    kubectl get ns "${SYSTEM_NAMESPACE}" >/dev/null 2>&1 || kubectl create ns "${SYSTEM_NAMESPACE}" >/dev/null 2>&1 || true
    drop_tenant_db "${T_DB_NAME}" "${SYSTEM_NAMESPACE}" || \
      warn "  check RDS manually for ${T_DB_NAME}."
  fi
elif [ "${KEEP_DB}" = false ]; then
  warn "DB_PASSWORD not set; skipping DB drop. Set it or drop ${T_DB_NAME} manually."
fi

# --- Step 3: remove this tenant's subs from the shared IRSA role trust policies ---
remove_irsa_trust() {
  local d="${REPO_ROOT}/infrastructure/terraform"
  terraform -chdir="$d" init -input=false >/dev/null 2>&1 || true
  local irsa_json; irsa_json="$(terraform -chdir="$d" output -json irsa_role_arns 2>/dev/null || echo "{}")"
  local oidc_url; oidc_url="$(terraform -chdir="${REPO_ROOT}/platform/terraform" output -raw oidc_provider_url 2>/dev/null || echo "")"
  # In-cluster fall back to the EKS API for the OIDC issuer (see deploy-tenant.sh).
  if [ -z "${oidc_url}" ]; then
    oidc_url="$(aws eks describe-cluster --name "${EKS_CLUSTER}" --region "${AWS_REGION}" \
      --query 'cluster.identity.oidc.issuer' --output text 2>/dev/null || echo "")"
  fi
  oidc_url="${oidc_url#https://}"
  [ -n "${oidc_url}" ] || { warn "OIDC URL unavailable; skipping IRSA trust cleanup."; return 0; }
  local svc role sub
  for svc in $(echo "${irsa_json}" | jq -r 'keys[]'); do
    role="otterworks-${svc}-dev"
    sub="system:serviceaccount:${NS}:${svc}"
    local doc; doc="$(aws iam get-role --role-name "${role}" --query 'Role.AssumeRolePolicyDocument' --output json 2>/dev/null || echo "")"
    [ -n "${doc}" ] || continue
    # Remove ONLY legacy per-tenant statements that pin this exact sub via
    # StringEquals (added by older deploys). Statements without a
    # StringEquals[:sub] — notably the shared Terraform-managed StringLike
    # wildcard statement that grants every otterworks-* namespace — MUST be left
    # untouched; stripping it would break AWS access for the golden app and all
    # other tenants. The current deploy relies on that wildcard and adds no
    # per-tenant StringEquals statement, so this is normally a no-op.
    local new; new="$(echo "${doc}" | jq --arg sub "${sub}" --arg url "${oidc_url}" '
      .Statement |= map(
        if (.Condition.StringEquals[$url+":sub"] // null) != null then
          select((.Condition.StringEquals[$url+":sub"]
            | (if type=="array" then . else [.] end) | index($sub)) | not)
        else . end)')"
    # Only update if something actually changed.
    if [ "$(echo "${doc}" | jq -cS .)" != "$(echo "${new}" | jq -cS .)" ]; then
      aws iam update-assume-role-policy --role-name "${role}" --policy-document "${new}" >/dev/null \
        && log "  IRSA trust: removed ${sub} from ${role}" \
        || warn "  failed to clean trust for ${role}"
    fi
  done
}
if [ "${KEEP_TRUST}" = false ]; then
  log "Cleaning tenant service-account subs from shared IRSA role trust policies..."
  remove_irsa_trust
fi

if [ -n "${TOKEN}" ]; then
  log "Deleting ECR image tags containing ${TOKEN}..."
  delete_token_ecr_tags "${TOKEN}"
  delete_host_dns
  delete_token_control_item "${TOKEN}"
  [ -n "${RDS_HOST:-}" ] || { [ -n "${DB_PASSWORD:-}" ] && load_infra_outputs; }
  TOKEN_DB_NAMES="${TOKEN_DB_NAMES:-${T_DB_NAME}}"
  token_residue "${TOKEN}" || { err "Teardown for ${ATTENDEE_ID} left resources bearing ${TOKEN}."; exit 1; }
fi

log "Teardown complete for tenant ${ATTENDEE_ID} (namespace ${NS})."
