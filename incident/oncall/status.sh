#!/usr/bin/env bash
# What the on-call storm is doing right now, per tenant: release revision and
# worker flag, seed counts, the k6 Job, firing storm alerts and Alertmanager
# groups. Read-only.
#
# Usage: incident/oncall/status.sh [oncall-before|oncall-after ...]
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_bins kubectl helm jq curl
ensure_kubeconfig
mapfile -t targets < <(tenants_or_both "$@")

telemetry=false
if kubectl -n "${MONITORING_NS}" get svc "${PROM_SVC}" "${AM_SVC}" >/dev/null 2>&1; then
  pf_prometheus
  pf_alertmanager
  telemetry=true
fi

for tenant in "${targets[@]}"; do
  ns="$(tenant_ns "${tenant}")"
  echo "== ${tenant} (${ns})  https://$(web_host "${tenant}")"
  if ! kubectl get ns "${ns}" >/dev/null 2>&1; then
    echo "   namespace missing; run make oncall-up"
    continue
  fi
  ready="$(kubectl -n "${ns}" get deploy -o json |
    jq -r '[.items[] | select((.status.readyReplicas // 0) >= 1)] | length as $r | "\($r)/\(.items | length)"')"
  echo "   deployments ready: ${ready}"
  echo "   document-service: rev $(helm_revision "${tenant}" || true), folderDigest.enabled=$(digest_enabled "${tenant}" || true)"
  if kubectl -n "${ns}" get deploy "${PG_DEPLOY}" >/dev/null 2>&1; then
    counts="$(pg "${tenant}" -At -c "SELECT format('documents=%s versions=%s fix_index=%s',
      (SELECT count(*) FROM documents), (SELECT count(*) FROM document_versions),
      (SELECT count(*) FROM pg_indexes WHERE indexname = '${FIX_INDEX}'))" 2>/dev/null || echo 'not migrated yet')"
    echo "   postgres: ${counts}"
  else
    echo "   postgres: ${PG_DEPLOY} not deployed"
  fi
  job="$(kubectl -n "${ns}" get job "${K6_JOB}" -o json 2>/dev/null |
    jq -r '"active=\(.status.active // 0) succeeded=\(.status.succeeded // 0) failed=\(.status.failed // 0) started=\(.status.startTime // "-")"' || true)"
  echo "   k6: ${job:-no ${K6_JOB} Job}"
  summary="$(kubectl -n "${ns}" logs "job/${K6_JOB}" --tail=5 2>/dev/null | sed -n 's/^K6_SUMMARY_JSON //p' | tail -n 1 || true)"
  [ -n "${summary}" ] && echo "   k6 summary: ${summary}"
  armed="$(state_get "${tenant}" .armed_at)"
  [ -n "${armed}" ] && echo "   armed at ${armed}, deploy rev $(state_get "${tenant}" .steps.deploy.revision) at $(state_get "${tenant}" .steps.deploy.at)"
  if [ "${telemetry}" = true ]; then
    prom_query "ALERTS{page=\"oncall\",namespace=\"${ns}\"}" |
      jq -r 'sort_by(.metric.service, .metric.alertname)[] |
        "   alert \(.metric.alertstate) \(.metric.alertname) service=\(.metric.service) severity=\(.metric.severity)"'
    curl -fsS --max-time 20 -G "http://localhost:${AM_PORT}/api/v2/alerts/groups" \
      --data-urlencode "filter=namespace=\"${ns}\"" --data-urlencode 'filter=page="oncall"' |
      jq -r '.[] | "   group receiver=\(.receiver.name) alerts=\(.alerts | length)"'
  else
    echo "   telemetry: Prometheus or Alertmanager port-forward unavailable"
  fi
done
