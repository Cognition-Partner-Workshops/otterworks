#!/usr/bin/env bash
# Replay the recorded storm page (fixtures/storm-payload.json) without arming
# anything. Timestamps are moved to now so the channel shows a fresh page.
#   - always: POST to the incident channel's /alertmanager (in-cluster, through
#     a port-forward)
#   - when ONCALL_DEVIN_WEBHOOK_URL is set: POST to that Devin automation, with
#     ONCALL_DEVIN_WEBHOOK_SECRET as X-Webhook-Secret. This starts a session.
#
# Usage: incident/oncall/simulate.sh [--print]
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_bins jq curl
fixture="${ONCALL_DIR}/fixtures/storm-payload.json"
now_s="$(date -u +%s)"
payload="$(jq -c --argjson now "${now_s}" '
  def iso($s): $s | todate;
  (.alerts | map(.startsAt | sub("\\.[0-9]+"; "") | fromdateiso8601) | max) as $last
  | .alerts |= map(.startsAt = iso((.startsAt | sub("\\.[0-9]+"; "") | fromdateiso8601) - $last + $now))' \
  "${fixture}")"

if [ "${1:-}" = --print ]; then
  jq . <<<"${payload}"
  exit 0
fi

require_bins kubectl
ensure_kubeconfig
pf_start "${PLATFORM_NS}" svc/incident-channel "${CHANNEL_PORT}" 8080 /healthz
code="$(printf '%s' "${payload}" | curl -sS --max-time 15 -o /dev/null -w '%{http_code}' \
  -H 'Content-Type: application/json' --data @- "http://localhost:${CHANNEL_PORT}/alertmanager")" || code=000
case "${code}" in 2*) log "Channel accepted the storm page (HTTP ${code})" ;;
  *) die "incident channel answered HTTP ${code}" ;; esac

if [ -n "${ONCALL_DEVIN_WEBHOOK_URL:-}" ]; then
  [ -n "${ONCALL_DEVIN_WEBHOOK_SECRET:-}" ] || die "ONCALL_DEVIN_WEBHOOK_SECRET is required with ONCALL_DEVIN_WEBHOOK_URL"
  code="$( { printf 'header = "X-Webhook-Secret: %s"\n' "${ONCALL_DEVIN_WEBHOOK_SECRET}"
             printf 'url = "%s"\n' "${ONCALL_DEVIN_WEBHOOK_URL}"; } |
    curl -sS --max-time 30 --config - -o /dev/null -w '%{http_code}' \
      -H 'Content-Type: application/json' --data "${payload}")" || code=000
  case "${code}" in 2*) log "Devin automation accepted the page (HTTP ${code}); a session is starting" ;;
    *) die "Devin automation answered HTTP ${code}" ;; esac
else
  log "ONCALL_DEVIN_WEBHOOK_URL not set; the Devin automation was not called"
fi
