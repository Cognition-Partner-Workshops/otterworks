#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/fixtures.sh"

minor=${1:-1.34}
case "$minor" in
  1.34|1.35) ;;
  *) printf 'Usage: %s [1.34|1.35]\n' "$0" >&2; exit 2 ;;
esac
cluster="devops-20261128-${minor//./-}"
context="kind-$cluster"
if kind get clusters | grep -Fxq "$cluster"; then
  printf 'Cluster %s exists; run down.sh %s to reset.\n' "$cluster" "$minor" >&2
  exit 2
fi

kind create cluster --name "$cluster" --config "$DEMO/kind/v$minor.yaml" --wait 120s
kubectl --context "$context" create namespace "$NAMESPACE"
kubectl --context "$context" label namespace "$NAMESPACE" run_token=DEVOPS_20261128
if [[ "$minor" == 1.35 ]]; then
  exit 0
fi

docker build --tag otterworks/devops-workload:fixture-v1 "$DEMO/kind/workload"
kind load docker-image otterworks/devops-workload:fixture-v1 --name "$cluster"

for workload in "${WORKLOADS[@]}"; do
  revision=$(git -C "$ROOT" log -1 --format=%H -- "$DEMO/values/common.yaml" "$DEMO/values/$workload.yaml")
  render_or_install upgrade "$workload" --install --kube-context "$context" --description "git $revision"
done
kubectl --context "$context" --namespace "$NAMESPACE" apply -f "$DEMO/kind/controls.yaml"
kubectl --context "$context" --namespace "$NAMESPACE" wait deployment --all --for=condition=Available --timeout=120s

if [[ -f "$DEMO/kind/observed.overlay.sh" ]]; then
  source "$DEMO/kind/observed.overlay.sh"
fi
