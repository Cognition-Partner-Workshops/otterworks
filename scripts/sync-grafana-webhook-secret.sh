#!/usr/bin/env bash
set -euo pipefail

ADMIN_NAMESPACE="${ADMIN_NAMESPACE:-otterworks}"
GRAFANA_NAMESPACE="${GRAFANA_NAMESPACE:-monitoring}"
ADMIN_SECRET="${ADMIN_SECRET:-admin-service-secrets}"
GRAFANA_SECRET="${GRAFANA_SECRET:-admin-alert-webhook}"

namespace="$(kubectl get namespace "${GRAFANA_NAMESPACE}" --ignore-not-found -o name)"
if [ -z "${namespace}" ]; then
  echo "No namespace ${GRAFANA_NAMESPACE}; webhook consumer not installed" >&2
  exit 0
fi

if [ -z "${GRAFANA_DEPLOYMENT:-}" ]; then
  deployments="$(kubectl -n "${GRAFANA_NAMESPACE}" get deployments -l app.kubernetes.io/name=grafana -o json)"
  count="$(jq '.items | length' <<< "${deployments}")"
  if [ "${count}" = 0 ]; then
    echo "No Grafana deployment in ${GRAFANA_NAMESPACE}; webhook consumer not installed" >&2
    exit 0
  fi
  [ "${count}" = 1 ] || { echo "Set GRAFANA_DEPLOYMENT to select the webhook consumer" >&2; exit 1; }
  GRAFANA_DEPLOYMENT="$(jq -r '.items[0].metadata.name' <<< "${deployments}")"
fi

# Copy only the webhook credential, never the admin JWT/database/session secrets.
kubectl -n "${ADMIN_NAMESPACE}" get secret "${ADMIN_SECRET}" -o json |
  jq -e --arg name "${GRAFANA_SECRET}" --arg namespace "${GRAFANA_NAMESPACE}" '
    if (.data.ALERT_WEBHOOK_SECRET // "") == "" then error("Missing webhook secret")
    else {apiVersion: "v1", kind: "Secret", type: "Opaque",
          metadata: {name: $name, namespace: $namespace},
          data: {ALERT_WEBHOOK_SECRET: .data.ALERT_WEBHOOK_SECRET}} end' |
  kubectl -n "${GRAFANA_NAMESPACE}" apply -f -
kubectl -n "${GRAFANA_NAMESPACE}" set env "deployment/${GRAFANA_DEPLOYMENT}" \
  --containers="${GRAFANA_CONTAINER:-grafana}" --from="secret/${GRAFANA_SECRET}"
# A same-name Secret update alone does not reload environment variables.
kubectl -n "${GRAFANA_NAMESPACE}" rollout restart "deployment/${GRAFANA_DEPLOYMENT}"
kubectl -n "${GRAFANA_NAMESPACE}" rollout status "deployment/${GRAFANA_DEPLOYMENT}" --timeout=180s
