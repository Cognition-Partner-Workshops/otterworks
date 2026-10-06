#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# OtterWorks - CloudWatch log shipping for tenant edge logs
#
# Installs one aws-for-fluent-bit DaemonSet in otterworks-system that ships the
# api-gateway and ingress-nginx access logs of every otterworks-* namespace to
#   /otterworks/eks/<cluster>/<namespace>/<container>     (7-day retention)
# and switches the shared ingress-nginx controller to a JSON access log so its
# lines can be filed per tenant. Nothing per tenant; new tenants are picked up
# by the DaemonSet as soon as their pods log.
#
# Prerequisite: the otterworks-fluent-bit-<env> IRSA role from
# infrastructure/terraform (module.irsa, service account "fluent-bit").
#
# Usage: ./scripts/install-log-shipping.sh            # idempotent
# ------------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/tenant-common.sh
source "${SCRIPT_DIR}/lib/tenant-common.sh"

CHART_VERSION="${FLUENT_BIT_CHART_VERSION:-0.2.0}"
LOG_NS="${SYSTEM_NAMESPACE}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
CHART_DIR="${REPO_ROOT}/infrastructure/helm/aws-for-fluent-bit"
ROLE_NAME="otterworks-fluent-bit-${ENVIRONMENT}"

require_bins kubectl helm aws

role_arn="$(aws iam get-role --role-name "${ROLE_NAME}" --query Role.Arn --output text 2>/dev/null || true)"
if [ -z "${role_arn}" ] || [ "${role_arn}" = "None" ]; then
  err "IAM role ${ROLE_NAME} not found; apply infrastructure/terraform (module.irsa) first."; exit 1
fi

log "Switching shared ingress-nginx to the JSON access log format..."
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx >/dev/null 2>&1 || true
helm upgrade ingress-nginx ingress-nginx/ingress-nginx -n "${INGRESS_NAMESPACE}" \
  --reuse-values -f "${REPO_ROOT}/infrastructure/helm/ingress-nginx/values-logging.yaml" \
  --wait --timeout 5m

kubectl get ns "${LOG_NS}" >/dev/null 2>&1 || kubectl create ns "${LOG_NS}"
kubectl -n "${LOG_NS}" create configmap fluent-bit-otterworks-lua \
  --from-file=otterworks.lua="${CHART_DIR}/otterworks.lua" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "${LOG_NS}" apply -f "${CHART_DIR}/networkpolicy.yaml"

log "Installing aws-for-fluent-bit ${CHART_VERSION} in ${LOG_NS} (role ${ROLE_NAME})..."
helm repo add eks https://aws.github.io/eks-charts >/dev/null 2>&1 || true
helm repo update eks >/dev/null 2>&1 || true
helm upgrade --install aws-for-fluent-bit eks/aws-for-fluent-bit \
  --version "${CHART_VERSION}" -n "${LOG_NS}" \
  -f "${CHART_DIR}/values.yaml" \
  --set-string "serviceAccount.annotations.eks\.amazonaws\.com/role-arn=${role_arn}" \
  --set-string "cloudWatchLogs.region=${AWS_REGION}" \
  --set-string "cloudWatchLogs.logGroupTemplate=/otterworks/eks/${EKS_CLUSTER}/\$cw_group" \
  --set-string "cloudWatchLogs.logGroupName=/otterworks/eks/${EKS_CLUSTER}/unrouted" \
  --wait --timeout 5m
# The Lua script is mounted from a ConfigMap the chart does not own; restart so
# a changed script is picked up.
kubectl -n "${LOG_NS}" rollout restart ds/aws-for-fluent-bit >/dev/null
kubectl -n "${LOG_NS}" rollout status ds/aws-for-fluent-bit --timeout=180s

log "Shipping to /otterworks/eks/${EKS_CLUSTER}/<namespace>/{api-gateway,ingress-nginx}"
