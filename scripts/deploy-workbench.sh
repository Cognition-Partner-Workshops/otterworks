#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TF_DIR="${REPO_ROOT}/demo-platform/infra/terraform"
CHART_DIR="${REPO_ROOT}/infrastructure/helm/workbench"
NAMESPACE="workbench"
SECRET_NAME="workbench-oidc"
AWS_REGION="${AWS_REGION:-us-east-1}"

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo "Usage: $0 <image-tag>" >&2
  exit 2
fi
IMAGE_TAG="$1"
for command in aws kubectl helm terraform openssl base64 jq; do
  command -v "${command}" >/dev/null 2>&1 || {
    echo "Required command not found: ${command}" >&2
    exit 1
  }
done

AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

secret_value() {
  local key="$1" response
  if response="$(kubectl -n "${NAMESPACE}" get secret "${SECRET_NAME}" -o "jsonpath={.data.${key}}" 2>&1)"; then
    if [ -n "${response}" ]; then
      printf '%s' "${response}" | base64 --decode
    fi
  elif [[ "${response}" != *NotFound* ]]; then
    echo "Could not read ${SECRET_NAME}: ${response}" >&2
    return 1
  fi
}

kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace "${NAMESPACE}" \
  app.kubernetes.io/managed-by=otterworks-workbench \
  platform/environment=dev \
  platform/team=otterworks \
  --overwrite

SESSION_SECRET="$(secret_value SESSION_SECRET)"
if [ -z "${SESSION_SECRET}" ]; then
  SESSION_SECRET="$(openssl rand -hex 32)"
fi
FIELDKIT_CLIENT_ID="${FIELDKIT_CLIENT_ID:-$(secret_value OIDC_CLIENT_ID)}"
FIELDKIT_CLIENT_SECRET="${FIELDKIT_CLIENT_SECRET:-$(secret_value OIDC_CLIENT_SECRET)}"

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: ${SECRET_NAME}
  namespace: ${NAMESPACE}
type: Opaque
data:
  SESSION_SECRET: $(printf '%s' "${SESSION_SECRET}" | base64 | tr -d '\n')
  OIDC_CLIENT_ID: $(printf '%s' "${FIELDKIT_CLIENT_ID}" | base64 | tr -d '\n')
  OIDC_CLIENT_SECRET: $(printf '%s' "${FIELDKIT_CLIENT_SECRET}" | base64 | tr -d '\n')
EOF

WORKBENCH_ROLE_ARN="$(terraform -chdir="${TF_DIR}" output -raw workbench_role_arn)"
if [ -z "${WORKBENCH_ROLE_ARN}" ] || [ "${WORKBENCH_ROLE_ARN}" = "null" ]; then
  echo "Terraform output workbench_role_arn is empty." >&2
  exit 1
fi

helm upgrade --install workbench "${CHART_DIR}" \
  --namespace "${NAMESPACE}" \
  --set-string image.repository="${ECR_REGISTRY}/otterworks/workbench" \
  --set-string image.tag="${IMAGE_TAG}" \
  --set-string serviceAccount.roleArn="${WORKBENCH_ROLE_ARN}" \
  --set-string awsRegion="${AWS_REGION}"
