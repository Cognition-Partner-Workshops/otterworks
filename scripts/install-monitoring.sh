#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_VERSION=65.8.1
NAMESPACE=monitoring

for bin in helm kubectl; do command -v "$bin" >/dev/null; done
# Credentials must already exist; never create or print webhook secrets here.
kubectl -n "$NAMESPACE" get secret monitoring-webhooks monitoring-grafana-admin >/dev/null
kubectl label namespace "$NAMESPACE" platform/team=otterworks --overwrite
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm repo update prometheus-community
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --version "$CHART_VERSION" --namespace "$NAMESPACE" \
  -f "$ROOT/infrastructure/helm/kube-prometheus-stack/values.yaml" \
  --wait --timeout 10m
helm upgrade --install otterworks-observability "$ROOT/infrastructure/helm/observability-rules" \
  --namespace "$NAMESPACE" --wait --timeout 5m
