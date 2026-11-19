#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
: "${BASE_URL:?Set BASE_URL to the external API origin of an isolated tenant}"
export NAMESPACE="${NAMESPACE:-otterworks-loadtest}"
export PROFILE="${PROFILE:-smoke}" USERS="${USERS:-10}" RATE="${RATE:-1}" VUS="${VUS:-1}" DURATION="${DURATION:-}"
export JOB_NAME="loadtest-$(date +%s)" BASE_URL
export DEADLINE="${DEADLINE:-10800}"
export TARGET_VUS="${TARGET_VUS:-50}" K6_OUT="${K6_OUT:-}"
case "$NAMESPACE" in otterworks-main|otterworks-platform|otterworks-system|default|kube-*|monitoring|ingress-nginx) echo 'Refusing protected namespace' >&2; exit 2;; esac
[[ "$NAMESPACE" =~ ^otterworks-[a-z0-9-]+$ ]] || { echo 'Use an existing isolated tenant namespace' >&2; exit 2; }
[[ "$BASE_URL" =~ ^https?://api-t-[a-z0-9-]+\.demo\.otterworks\.app$ ]] || { echo 'Use a dedicated tenant API hostname' >&2; exit 2; }
[[ "$BASE_URL" != *api-t-main.* ]] || { echo 'Never target main from the cluster runner' >&2; exit 2; }
command -v envsubst >/dev/null
kubectl get namespace "$NAMESPACE" >/dev/null
mkdir -p tests/load/k6/results
kubectl -n "$NAMESPACE" create configmap "$JOB_NAME" --from-file=tests/load/k6/otterworks.js --from-file=tests/load/k6/busy-season.js --from-file=tests/load/k6/lib/config.js --from-file=tests/load/k6/lib/auth.js --from-file=tests/load/k6/lib/http.js
envsubst '${JOB_NAME} ${NAMESPACE} ${BASE_URL} ${PROFILE} ${USERS} ${RATE} ${VUS} ${DURATION} ${DEADLINE} ${TARGET_VUS} ${K6_OUT}' < tests/load/k6/k8s/job.yaml | kubectl apply -f -
kubectl -n "$NAMESPACE" wait --for=condition=Ready pod -l "job-name=$JOB_NAME" --timeout=180s
pod="$(kubectl -n "$NAMESPACE" get pod -l "job-name=$JOB_NAME" -o jsonpath='{.items[0].metadata.name}')"
echo "Running $JOB_NAME; results survive in the pod until collection or deadline."
kubectl -n "$NAMESPACE" logs -f "$pod" &
logs_pid=$!
trap 'kill "$logs_pid" 2>/dev/null || true' EXIT
kubectl -n "$NAMESPACE" exec "$pod" -- sh -c 'until [ -f /work/finished ]; do sleep 5; done'
kubectl -n "$NAMESPACE" exec "$pod" -- cat /work/results.tar.gz > "tests/load/k6/results/$JOB_NAME.tar.gz"
tar -xzf "tests/load/k6/results/$JOB_NAME.tar.gz"
code="$(kubectl -n "$NAMESPACE" logs "$pod" | sed -n 's/^K6_EXIT_CODE=//p' | tail -1)"
kubectl -n "$NAMESPACE" exec "$pod" -- touch /work/collected
kubectl -n "$NAMESPACE" delete configmap "$JOB_NAME"
exit "${code:-1}"
