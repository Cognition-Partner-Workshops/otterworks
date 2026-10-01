#!/usr/bin/env bash
set -euo pipefail
set +x

HERE="$(cd "$(dirname "$0")" && pwd)"
for tool in kubectl docker python3 sha256sum; do
  command -v "$tool" >/dev/null || { echo "Required tool: $tool" >&2; exit 1; }
done
PYTHON=python3
if ! python3 -c 'import yaml' 2>/dev/null; then
  VENV="${ONCALL_PLATFORM_VENV:-$HOME/.cache/oncall-platform-venv}"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -r "$HERE/requirements.txt"
  PYTHON="$VENV/bin/python"
fi
kubectl get namespace monitoring >/dev/null
"$PYTHON" "$HERE/merge-alertmanager-routes.py"

for component in loki tempo alloy; do
  config="$component.yaml"
  key="$component.yaml"
  if [[ "$component" == alloy ]]; then config=alloy.alloy; key=config.alloy; fi
  kubectl -n monitoring create configmap "oncall-$component" \
    --from-file="$key=$HERE/$config" --dry-run=client -o yaml | kubectl apply -f -
done
kubectl apply -f "$HERE/workloads.yaml" -f "$HERE/datasources.yaml" -f "$HERE/postgres-podmonitor.yaml"
for component in loki tempo alloy; do
  workload="deployment/oncall-$component"
  config="$HERE/$component.yaml"
  if [[ "$component" == alloy ]]; then
    workload=daemonset/oncall-alloy
    config="$HERE/alloy.alloy"
  fi
  checksum="$(sha256sum "$config")"
  checksum="${checksum%% *}"
  kubectl -n monitoring patch "$workload" --type=merge \
    --patch "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"checksum/config\":\"$checksum\"}}}}}"
  kubectl -n monitoring rollout status "$workload" --timeout=180s
done
"$PYTHON" "$HERE/patch-otel-tempo.py" --apply
"$PYTHON" "$HERE/merge-alertmanager-routes.py" --apply
