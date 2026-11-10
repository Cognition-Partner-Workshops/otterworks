#!/usr/bin/env bash
# tenant_redis <namespace> <redis-cli args...>
#
# Runs redis-cli against the tenant's in-cluster Redis from a short-lived pod in
# that namespace and prints its output. Callers need pod create/get/log/delete
# only; nothing here requires pods/exec.
tenant_redis() {
  local ns="$1"; shift
  local pod="redis-cli-$(date +%s)-${RANDOM}" phase="" i
  kubectl -n "${ns}" run "${pod}" --restart=Never --quiet \
    --image="${TENANT_REDIS_IMAGE:-redis:7-alpine}" \
    --labels=app.kubernetes.io/name=redis-cli \
    --override-type=strategic \
    --overrides='{"apiVersion":"v1","spec":{"automountServiceAccountToken":false,"securityContext":{"runAsNonRoot":true,"runAsUser":999,"runAsGroup":999,"seccompProfile":{"type":"RuntimeDefault"}}}}' \
    --command -- redis-cli -h redis "$@" >/dev/null || return 1
  for i in $(seq 1 "${TENANT_REDIS_TIMEOUT:-60}"); do
    phase="$(kubectl -n "${ns}" get pod "${pod}" -o jsonpath='{.status.phase}' 2>/dev/null)"
    case "${phase}" in Succeeded|Failed) break ;; esac
    sleep 1
  done
  kubectl -n "${ns}" logs "${pod}" 2>/dev/null
  kubectl -n "${ns}" delete pod "${pod}" --wait=false >/dev/null 2>&1 || true
  [ "${phase}" = "Succeeded" ]
}
