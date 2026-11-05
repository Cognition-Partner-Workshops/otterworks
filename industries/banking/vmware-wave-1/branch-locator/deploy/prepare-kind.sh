#!/usr/bin/env bash
set -euo pipefail
cluster="${KIND_CLUSTER:?set KIND_CLUSTER}"
[[ "$(kubectl config current-context)" == "kind-$cluster" ]] || { echo "wrong kubectl context" >&2; exit 1; }
here="$(cd "$(dirname "$0")" && pwd)"
kubectl create namespace deps --dry-run=client -o yaml | kubectl apply -f -
sed 's/^branch-db\.//' "$here/kind-secrets.env" | \
  kubectl create secret generic branch-db -n deps --from-env-file=/dev/stdin --dry-run=client -o yaml | kubectl apply -f -
