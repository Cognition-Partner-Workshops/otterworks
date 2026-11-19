#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

check_chart() {
  local chart="$1"; shift
  echo "Checking chart: $chart"
  helm lint "$chart" "$@"
  helm template prometheus "$chart" --namespace otterworks-ci \
    --kube-version 1.30.0 --api-versions monitoring.coreos.com/v1 "$@" \
    | tee "$WORK/rendered.yaml" \
    | kubeconform -strict -summary -kubernetes-version 1.30.0 -ignore-missing-schemas
  python3 "$ROOT/scripts/check-observability-manifests.py" < "$WORK/rendered.yaml"
}

for chart in "$ROOT"/infrastructure/helm/*; do
  [ -f "$chart/Chart.yaml" ] || continue
  args=()
  case "$(basename "$chart")" in
    db2-archive)
      args+=(--set namespaceToken=ci1-after --set pv.volumeName=pv-ci) ;;
    oracle-archive)
      args+=(--set namespaceToken=ci1-after --set pv.volumeName=pv-ci
             --set initJob.image.repository=ci/ldm-job --set initJob.image.tag=ci) ;;
    migration-job)
      args+=(--set namespaceToken=ci1-after --set stage=extract --set runId=ci
             --set image.tag=ci --set expires=2026-01-01T00:00:00Z
             --set-file manifest.base="$ROOT/migration/manifest.yaml"
             --set-file manifest.overlay="$ROOT/migration/manifests/d24-after.yaml") ;;
    observability-rules) ;;
    *)
      args+=(--set image.repository=example.invalid/ci --set image.tag=ci)
      if [ "$(basename "$chart")" = document-service ]; then
        args+=(--set monitoring.rules.enabled=true --set monitoring.dashboard.enabled=true
               --set tracing.enabled=true)
      fi ;;
  esac
  check_chart "$chart" "${args[@]}"
done

# Values-only directories are overlays, not local charts. Validate the pinned
# upstream stack as well; Fluent Bit/ingress overlays remain owned by their installers.
if [ -z "${KPS_CHART:-}" ]; then
  helm pull kube-prometheus-stack --repo https://prometheus-community.github.io/helm-charts \
    --version 65.8.1 --untar --untardir "$WORK"
  KPS_CHART="$WORK/kube-prometheus-stack"
fi
check_chart "$KPS_CHART" -f "$ROOT/infrastructure/helm/kube-prometheus-stack/values.yaml"
echo "All local charts and pinned monitoring stack passed Helm/kubeconform checks"
