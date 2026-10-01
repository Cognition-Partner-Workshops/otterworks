#!/usr/bin/env bash
# shellcheck disable=SC2016 # jq filters are single-quoted on purpose
# Fail-closed gate for the on-call storm, driven by faults.yaml.
#   before: at least 10 of the 12 storm alerts firing across all 4 services,
#           Alertmanager holding exactly one oncall-devin group for the namespace,
#           and that group paged after this arm's deploy
#   after:  the same load running, the worker on, no storm alert firing, and the
#           folder-list p95 under the SLO
# Writes incident/oncall/reports/<tenant>-<expect>-<utc>.json. Exit 0 = green.
#
# Usage: incident/oncall/verify.sh <oncall-before|oncall-after> <before|after>
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

tenant="${1:-}"
expect="${2:-}"
require_tenant "${tenant}"
case "${expect}" in before|after) ;; *) die "usage: $0 <tenant> before|after" ;; esac
require_bins kubectl helm jq curl python3
python3 -c 'import yaml' 2>/dev/null || die "python3 needs PyYAML to read faults.yaml"
ensure_kubeconfig
ns="$(tenant_ns "${tenant}")"
require_ns "${ns}"

faults="$(python3 -c 'import json, sys, yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1]))))' \
  "${ONCALL_DIR}/faults.yaml")"
f() { jq -r "$1" <<<"${faults}"; }

pf_prometheus
pf_alertmanager

checks='[]'
check() { # check <ok:true|false> <message>
  checks="$(jq -c --argjson ok "$1" --arg msg "$2" '. + [{ok: $ok, check: $msg}]' <<<"${checks}")"
  if [ "$1" = true ]; then echo "PASS $2"; else echo "FAIL $2"; fi
}

firing="$(prom_query "ALERTS{alertstate=\"firing\",page=\"oncall\",namespace=\"${ns}\"}")"
firing_names="$(jq -c '[.[].metric.alertname] | unique' <<<"${firing}")"
measures='{}'

if [ "${expect}" = before ]; then
  expected_names="$(f '[.expected.alerts[].name]' | jq -c .)"
  hits="$(jq -n --argjson a "${expected_names}" --argjson b "${firing_names}" '[$a[] | select(. as $x | $b | index($x))]')"
  n_hits="$(jq length <<<"${hits}")"
  min_firing="$(f .gates.before.min_firing)"
  check "$([ "${n_hits}" -ge "${min_firing}" ] && echo true || echo false)" \
    "storm alerts firing in ${ns}: ${n_hits} of $(jq length <<<"${expected_names}") (need >= ${min_firing})"

  services="$(jq -c --argjson want "$(f '.expected.services' | jq -c .)" \
    '[.[].metric.service] | unique | map(select(. as $s | $want | index($s)))' <<<"${firing}")"
  n_services="$(jq length <<<"${services}")"
  want_services="$(f .gates.before.services)"
  check "$([ "${n_services}" -ge "${want_services}" ] && echo true || echo false)" \
    "services paging: ${n_services} of ${want_services} ($(jq -r 'join(", ")' <<<"${services}"))"

  receiver="${ONCALL_VERIFY_RECEIVER:-$(f .expected.receiver)}"
  groups="$(curl -fsS --max-time 20 -G "http://localhost:${AM_PORT}/api/v2/alerts/groups" \
    --data-urlencode "filter=namespace=\"${ns}\"" --data-urlencode 'filter=page="oncall"' \
    --data-urlencode "receiver=${receiver}")"
  n_groups="$(jq --arg r "${receiver}" --arg ns "${ns}" \
    '[.[] | select(.receiver.name == $r and .labels.namespace == $ns)] | length' <<<"${groups}")"
  want_groups="$(f .gates.before.devin_groups)"
  check "$([ "${n_groups}" -eq "${want_groups}" ] && echo true || echo false)" \
    "Alertmanager groups for ${receiver} in ${ns}: ${n_groups} (need exactly ${want_groups})"

  # This arm's config deploy: .state when this checkout armed the tenant and its
  # oncall_run is still the live one, otherwise Helm (a paged session's fresh
  # clone). The Helm record is cached back into .state.
  live_run="$(helm -n "${ns}" get values document-service -o json 2>/dev/null |
    jq -r '.monitoring.rules.extraLabels.oncall_run // empty')"
  deployed_at="$(state_get "${tenant}" .steps.deploy.at)"
  run="$(state_get "${tenant}" .steps.deploy.oncall_run)"
  reloaded_at="$(state_get "${tenant}" .steps.deploy.alertmanager_reloaded_at)"
  lingered="$(state_get "${tenant}" .steps.deploy.previous_group_may_linger)"
  deploy_source=.state
  if [ -z "${deployed_at}" ] || [ -z "${run}" ] || [ "${run}" != "${live_run}" ]; then
    deployed_at=""
    run=""
    reloaded_at=""
    lingered=""
    deploy_source=none
    record="$(cluster_deploy_record "${tenant}")"
    if [ -n "${record}" ]; then
      deploy_source=helm
      deployed_at="$(jq -r .at <<<"${record}")"
      run="$(jq -r .oncall_run <<<"${record}")"
      deploy_epoch="$(date -u -d "${deployed_at}" +%s)"
      # arm.sh takes oncall_run from the clock right before it checks for a
      # lingering group and reloads Alertmanager, then runs helm upgrade.
      if [[ "${run}" =~ ^[0-9]+$ ]]; then
        reloaded_at="$(am_reloaded_between "${run}" "${deploy_epoch}")"
        if oncall_group_may_linger "${ns}" "${run}"; then lingered=true; else lingered=false; fi
      fi
      state_update "${tenant}" \
        '.steps.deploy = {at: $at, release: "document-service", revision: $rev, oncall_run: $run,
                          previous_group_may_linger: $linger, alertmanager_reloaded_at: $reload, source: "helm"}' \
        --arg at "${deployed_at}" --argjson rev "$(jq .revision <<<"${record}")" --arg run "${run}" \
        --argjson linger "${lingered:-null}" --arg reload "${reloaded_at}"
    fi
  fi
  echo "INFO config deploy from ${deploy_source}: at ${deployed_at:-unknown}, oncall_run ${run:-unset}"
  first_start="$(jq -r --arg r "${receiver}" --arg ns "${ns}" \
    '[.[] | select(.receiver.name == $r and .labels.namespace == $ns) | .alerts[].startsAt] | sort | first // empty' <<<"${groups}")"
  if [ -n "${deployed_at}" ] && [ -n "${first_start}" ]; then
    lag=$(( $(date -u -d "${first_start}" +%s) - $(date -u -d "${deployed_at}" +%s) ))
    within="$(f .expected.alerts_within_seconds)"
    check "$([ "${lag}" -le "${within}" ] && echo true || echo false)" \
      "first storm alert ${lag}s after the config deploy (need <= ${within}s)"
    measures="$(jq -c --argjson lag "${lag}" '.seconds_deploy_to_first_alert = $lag' <<<"${measures}")"
  else
    echo "INFO no deploy record (.state or Helm) or no alert yet; time-to-page not measured"
  fi

  # A page delivered after this arm's deploy, not just a group that exists:
  # Alertmanager's notification log suppresses a storm whose alerts it already
  # paged, and that suppressed group still shows up above.
  n_run="$(jq --arg r "${receiver}" --arg ns "${ns}" --arg run "${run}" \
    '[.[] | select(.receiver.name == $r and .labels.namespace == $ns) | .alerts[]
      | select($run != "" and .labels.oncall_run == $run)] | length' <<<"${groups}")"
  check "$([ -n "${run}" ] && [ "${n_run}" -ge 1 ] && echo true || echo false)" \
    "alerts from this arm (oncall_run=${run:-unset}) in the ${receiver} group: ${n_run}"
  page_ok=false
  page_msg="no deploy record in .state or Helm; cannot tell whether ${receiver} paged for this arm"
  sent_since=""
  if [ -n "${deployed_at}" ]; then
    deploy_epoch="$(date -u -d "${deployed_at}" +%s)"
    now_epoch="$(date +%s)"
    sent_q="sum(alertmanager_notifications_total{integration=\"webhook\",receiver=\"${receiver}\"})"
    sent_now="$(prom_scalar_at "${sent_q}" "${now_epoch}")"
    if [ -n "${sent_now}" ]; then
      sent_then="$(prom_scalar_at "${sent_q}" "${deploy_epoch}")"
      sent_since="$(awk -v a="${sent_now}" -v b="${sent_then:-0}" 'BEGIN { printf "%d", a - b }')"
      [ "${sent_since}" -ge 1 ] && page_ok=true
      page_msg="${receiver} webhook notifications since the deploy at ${deployed_at}: ${sent_since} (need >= 1)"
    else
      # Alertmanager runs without --enable-feature=receiver-name-in-metrics, so
      # its counters cannot tell receivers apart. Infer the page instead: arm.sh
      # reloaded Alertmanager before the deploy whenever an older group could
      # still be held, so the group holding this arm's alerts is new and
      # flushes once group_wait passes.
      sent_q='sum(alertmanager_notifications_total{integration="webhook"})'
      sent_now="$(prom_scalar_at "${sent_q}" "${now_epoch}")"
      sent_then="$(prom_scalar_at "${sent_q}" "${deploy_epoch}")"
      sent_since="$(awk -v a="${sent_now:-0}" -v b="${sent_then:-0}" 'BEGIN { printf "%d", a - b }')"
      group_wait="$(am_route_seconds "${receiver}" group_wait)"
      due=""
      if [ -n "${first_start}" ] && [ -n "${group_wait}" ]; then
        due=$(( $(date -u -d "${first_start}" +%s) + group_wait ))
      fi
      if { [ -n "${reloaded_at}" ] || [ "${lingered}" = false ]; } && [ -n "${due}" ] && [ "${n_run}" -ge 1 ] &&
         [ $(( now_epoch - due )) -ge 60 ] && [ "${sent_since}" -ge 1 ]; then
        page_ok=true
      fi
      page_msg="${receiver} page for this arm (inferred: Alertmanager reloaded ${reloaded_at:-no, no earlier group}, group_wait ${group_wait:-?}s"
      page_msg+=" due $( [ -n "${due}" ] && date -u -d "@${due}" +%H:%M:%SZ || echo never), webhook notifications since deploy ${sent_since})"
    fi
  fi
  check "${page_ok}" "${page_msg}"
  measures="$(jq -c --argjson n "${firing_names}" --argjson g "${n_groups}" --arg run "${run}" \
    --arg sent "${sent_since}" --argjson page "${page_ok}" --arg src "${deploy_source}" \
    '.firing = $n | .devin_groups = $g | .oncall_run = $run | .devin_paged = $page
     | .webhook_notifications_since_deploy = $sent | .deploy_record_source = $src' <<<"${measures}")"
else
  window="$(f .gates.after.window)"
  handler="$(f .gates.after.handler)"
  sel="namespace=\"${ns}\",handler=\"${handler}\",method=\"GET\""

  started="$(kubectl -n "${ns}" get job "${K6_JOB}" -o jsonpath='{.status.startTime}' 2>/dev/null || true)"
  active="$(kubectl -n "${ns}" get job "${K6_JOB}" -o jsonpath='{.status.active}' 2>/dev/null || true)"
  soak="${ONCALL_VERIFY_SOAK_SECONDS:-$(f .gates.after.soak_seconds)}"
  ran=0
  [ -n "${started}" ] && ran=$(( $(date +%s) - $(date -u -d "${started}" +%s) ))
  check "$([ "${active:-0}" -ge 1 ] && [ "${ran}" -ge "${soak}" ] && echo true || echo false)" \
    "k6 load running in ${ns} for ${ran}s (need an active ${K6_JOB} for >= ${soak}s)"
  check "$([ "$(digest_enabled "${tenant}")" = true ] && echo true || echo false)" \
    "folder digest worker enabled on document-service (same conditions as before)"

  n_firing="$(jq length <<<"${firing_names}")"
  max_firing="$(f .gates.after.max_firing)"
  check "$([ "${n_firing}" -le "${max_firing}" ] && echo true || echo false)" \
    "storm alerts firing in ${ns}: ${n_firing} $(jq -r 'if length > 0 then "(" + join(", ") + ")" else "" end' <<<"${firing_names}")"

  p95="$(prom_query "histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{${sel}}[${window}])))" |
    jq -r '.[0].value[1] // "NaN"')"
  slo="$(f .gates.after.p95_seconds_max)"
  check "$(awk -v v="${p95}" -v s="${slo}" 'BEGIN { print (v != "NaN" && v + 0 <= s + 0) ? "true" : "false" }')" \
    "folder list p95 ${p95}s over ${window} (need <= ${slo}s)"

  rate="$(prom_query "sum(rate(http_request_duration_seconds_count{${sel}}[${window}]))" |
    jq -r '.[0].value[1] // "0"')"
  min_rate="$(f .gates.after.min_request_rate)"
  check "$(awk -v v="${rate}" -v s="${min_rate}" 'BEGIN { print (v + 0 >= s + 0) ? "true" : "false" }')" \
    "folder list rate ${rate}/s at document-service (need >= ${min_rate}/s)"
  measures="$(jq -c --arg p "${p95}" --arg r "${rate}" --argjson n "${firing_names}" \
    '.p95_seconds = $p | .request_rate = $r | .firing = $n' <<<"${measures}")"
fi

ok="$(jq 'all(.ok)' <<<"${checks}")"
mkdir -p "${REPORT_DIR}"
report="${REPORT_DIR}/${tenant}-${expect}-$(date -u +%Y%m%dT%H%M%SZ).json"
jq -n --arg t "${tenant}" --arg ns "${ns}" --arg e "${expect}" --arg at "$(now_iso)" \
  --arg run "${RUN_ID}" --argjson ok "${ok}" --argjson checks "${checks}" --argjson m "${measures}" \
  '{tenant: $t, namespace: $ns, expect: $e, at: $at, run_id: $run, ok: $ok, checks: $checks, measures: $m}' >"${report}"
state_update "${tenant}" '.verify[$e] = {at: $at, ok: $ok, report: $r}' \
  --arg e "${expect}" --arg at "$(now_iso)" --argjson ok "${ok}" --arg r "${report#"${REPO}"/}"

if [ "${ok}" = true ]; then
  log "GREEN ${tenant} EXPECT=${expect} (report ${report#"${REPO}"/})"
else
  log "RED ${tenant} EXPECT=${expect} (report ${report#"${REPO}"/})"
  exit 1
fi
