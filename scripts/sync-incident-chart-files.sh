#!/usr/bin/env bash
# Keep chart copies of incident/security alert rules and the incident
# dashboard identical to their sources. Helm's .Files.Get cannot read outside
# the chart directory, so the chart carries generated copies.
#
#   scripts/sync-incident-chart-files.sh          # copy sources into the chart
#   scripts/sync-incident-chart-files.sh --check  # fail if a copy has drifted
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PAIRS=(
  "observability/prometheus/incident_alerts.yml:infrastructure/helm/document-service/files/incident_alerts.yml"
  "observability/grafana/dashboards/incident-responder.json:infrastructure/helm/document-service/files/incident-responder.json"
  "observability/prometheus/security_alerts.yml:infrastructure/helm/api-gateway/files/security_alerts.yml"
)

check=false
[ "${1:-}" = "--check" ] && check=true

rc=0
for pair in "${PAIRS[@]}"; do
  src="${REPO_ROOT}/${pair%%:*}"
  dst="${REPO_ROOT}/${pair##*:}"
  if "${check}"; then
    if ! cmp -s "${src}" "${dst}"; then
      echo "drift: ${dst#"${REPO_ROOT}"/} differs from ${pair%%:*} (run scripts/sync-incident-chart-files.sh)" >&2
      rc=1
    fi
  else
    mkdir -p "$(dirname "${dst}")"
    cp "${src}" "${dst}"
    echo "synced ${pair%%:*} -> ${dst#"${REPO_ROOT}"/}"
  fi
done
exit "${rc}"
