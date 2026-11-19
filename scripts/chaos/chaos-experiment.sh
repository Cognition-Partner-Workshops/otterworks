#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# OtterWorks - tenant-scoped chaos experiments with a steady-state check.
#
# Each run: probe the tenant's API through the shared ingress for a baseline,
# inject one fault, keep probing, roll the fault back, wait for recovery, and
# print availability, worst latency and time-to-recover. Nothing outside the
# tenant namespace is touched unless --allow-cluster-impact is given.
#
# Usage:
#   scripts/chaos/chaos-experiment.sh <ATTENDEE_ID> pod-kill <service>
#   scripts/chaos/chaos-experiment.sh <ATTENDEE_ID> dependency-outage <redis|meilisearch>
#   scripts/chaos/chaos-experiment.sh <ATTENDEE_ID> cpu-stress <service>
#   scripts/chaos/chaos-experiment.sh <ATTENDEE_ID> scenario <bug-catalog scenario>
#   scripts/chaos/chaos-experiment.sh <ATTENDEE_ID> node-drain --allow-cluster-impact
#
# Env: DURATION (fault window, s, default 60), BASELINE (s, default 20),
#      PROBE_URL (default https://<tenant api host>/health), SLO_AVAILABILITY (default 0.99)
#
# t-main (otterworks-main) is refused: AGENTS.md forbids injecting faults there.
# ------------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=SCRIPTDIR/../lib/tenant-common.sh
source "${REPO_ROOT}/scripts/lib/tenant-common.sh"

ATTENDEE_ID="${1:-}"; EXPERIMENT="${2:-}"; TARGET="${3:-}"
[ -n "${ATTENDEE_ID}" ] && [ -n "${EXPERIMENT}" ] || { sed -n 2,22p "$0"; exit 1; }
ALLOW_CLUSTER=false
for a in "$@"; do [ "$a" = "--allow-cluster-impact" ] && ALLOW_CLUSTER=true; done

require_bins kubectl curl
NS="$(tenant_namespace "${ATTENDEE_ID}")"
[ "${NS}" != "otterworks-main" ] || { err "Refusing to run chaos against t-main. Use a workshop-<id> tenant."; exit 1; }
kubectl get ns "${NS}" >/dev/null 2>&1 || { err "Namespace ${NS} not found (deploy it with scripts/deploy-tenant.sh)."; exit 1; }

DURATION="${DURATION:-60}"; BASELINE="${BASELINE:-20}"; SLO="${SLO_AVAILABILITY:-0.99}"
if [ -z "${PROBE_URL:-}" ]; then
  API_HOST="$(kubectl get ingress -n "${NS}" -o jsonpath='{range .items[*].spec.rules[*]}{.host}{"\n"}{end}' | grep '^api-' | head -1 || true)"
  [ -n "${API_HOST}" ] || { err "No api-* ingress host in ${NS}; set PROBE_URL."; exit 1; }
  PROBE_URL="https://${API_HOST}/health"
fi
LOG="$(mktemp -t chaos-XXXX.log)"

probe_loop() {  # appends "<epoch> <http_code> <seconds>" once per second
  while :; do
    printf '%s %s\n' "$(date +%s)" "$(curl -s -o /dev/null -m 5 -w '%{http_code} %{time_total}' "${PROBE_URL}" || echo '000 5')" >> "${LOG}"
    sleep 1
  done
}

ROLLBACK=":"
cleanup() { eval "${ROLLBACK}" || true; [ -n "${PROBER:-}" ] && kill "${PROBER}" 2>/dev/null || true; }
trap cleanup EXIT

wait_ready() {  # $1 = label selector; returns seconds until all pods are Ready
  local start; start=$(date +%s)
  kubectl rollout status deploy -n "${NS}" -l "$1" --timeout=10m >/dev/null 2>&1 || \
    kubectl wait pod -n "${NS}" -l "$1" --for=condition=Ready --timeout=10m >/dev/null
  echo $(( $(date +%s) - start ))
}

log "${EXPERIMENT} in ${NS} (probe ${PROBE_URL}, fault window ${DURATION}s)"
probe_loop & PROBER=$!
sleep "${BASELINE}"
FAULT_START=$(date +%s)

case "${EXPERIMENT}" in
  pod-kill)
    [ -n "${TARGET}" ] || { err "pod-kill needs a service"; exit 1; }
    SEL="app.kubernetes.io/name=${TARGET}"
    kubectl delete pod -n "${NS}" -l "${SEL}" --wait=false
    sleep 2
    RECOVER_S=$(wait_ready "${SEL}")
    ;;
  dependency-outage)
    [[ "${TARGET}" =~ ^(redis|meilisearch)$ ]] || { err "dependency-outage needs redis|meilisearch"; exit 1; }
    ROLLBACK="kubectl scale deploy/${TARGET} -n ${NS} --replicas=1"
    kubectl scale "deploy/${TARGET}" -n "${NS}" --replicas=0
    sleep "${DURATION}"
    eval "${ROLLBACK}"; ROLLBACK=":"
    kubectl rollout status "deploy/${TARGET}" -n "${NS}" --timeout=5m >/dev/null
    RECOVER_S=$(( $(date +%s) - FAULT_START - DURATION ))
    ;;
  cpu-stress)
    [ -n "${TARGET}" ] || { err "cpu-stress needs a service"; exit 1; }
    POD="$(kubectl get pod -n "${NS}" -l "app.kubernetes.io/name=${TARGET}" -o jsonpath='{.items[0].metadata.name}')"
    # Busy-loop inside the container up to its CPU limit; exits on its own.
    kubectl exec -n "${NS}" "${POD}" -- sh -c "timeout ${DURATION} sh -c 'while :; do :; done' & timeout ${DURATION} sh -c 'while :; do :; done'; true"
    RECOVER_S=0
    ;;
  scenario)
    [ -n "${TARGET}" ] || { err "scenario needs a scripts/bug-catalog.yaml scenario"; exit 1; }
    ROLLBACK="${REPO_ROOT}/scripts/inject-bug.sh ${ATTENDEE_ID} reset"
    "${REPO_ROOT}/scripts/inject-bug.sh" "${ATTENDEE_ID}" "${TARGET}"
    sleep "${DURATION}"
    eval "${ROLLBACK}"; ROLLBACK=":"
    RECOVER_S=0
    ;;
  node-drain)
    [ "${ALLOW_CLUSTER}" = true ] || { err "node-drain evicts every tenant's pods on that node; pass --allow-cluster-impact"; exit 1; }
    NODE="$(kubectl get pod -n "${NS}" -l app.kubernetes.io/name=api-gateway -o jsonpath='{.items[0].spec.nodeName}')"
    ROLLBACK="kubectl uncordon ${NODE}"
    kubectl drain "${NODE}" --ignore-daemonsets --delete-emptydir-data --timeout=5m
    RECOVER_S=$(wait_ready "app.kubernetes.io/name=api-gateway")
    sleep "${DURATION}"
    eval "${ROLLBACK}"; ROLLBACK=":"
    ;;
  *) err "unknown experiment ${EXPERIMENT}"; exit 1 ;;
esac

sleep 15
kill "${PROBER}" 2>/dev/null || true; PROBER=""

awk -v fs="${FAULT_START}" -v slo="${SLO}" -v rec="${RECOVER_S}" '
  { t=$1; ok=($2 ~ /^2/); lat=$3
    if (t < fs) { bn++; bok+=ok } else { fn++; fok+=ok; if (lat>worst) worst=lat; if (!ok) { if (!first) first=t; last=t } } }
  END {
    ba = bn ? bok/bn : 0; fa = fn ? fok/fn : 0
    printf "baseline availability : %.2f%% (%d probes)\n", 100*ba, bn
    printf "fault availability    : %.2f%% (%d probes)\n", 100*fa, fn
    printf "worst latency         : %.2fs\n", worst
    printf "error window          : %ds\n", first ? last-first+1 : 0
    printf "pods ready again after: %ss\n", rec
    if (fa >= slo) { print "RESULT: PASS (steady state held)" } else { print "RESULT: FAIL (availability below SLO " slo*100 "%)"; exit 2 }
  }' "${LOG}"
