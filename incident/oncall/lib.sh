#!/usr/bin/env bash
# Shared helpers for the on-call alert storm harness. Sourced, never executed.
# Conventions follow incident/tenant.sh and scripts/lib/tenant-common.sh:
# namespace-per-tenant, fail-closed port-forwards, secrets read from Kubernetes
# and passed by stdin or environment, never on argv and never printed.

ONCALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${ONCALL_DIR}/../.." && pwd)"
STATE_DIR="${ONCALL_STATE_DIR:-${ONCALL_DIR}/.state}"
REPORT_DIR="${ONCALL_REPORT_DIR:-${ONCALL_DIR}/reports}"
CHART_DIR="${REPO}/infrastructure/helm/document-service"
export ONCALL_DIR REPO STATE_DIR REPORT_DIR CHART_DIR

MONITORING_NS="${MONITORING_NS:-monitoring}"
PLATFORM_NS="${PLATFORM_NS:-otterworks-platform}"
PROM_SVC="${PROM_SVC:-prometheus-prometheus}"
AM_SVC="${AM_SVC:-prometheus-alertmanager}"
GRAFANA_SVC="${GRAFANA_SVC:-prometheus-grafana}"
PROM_PORT="${ONCALL_PROM_PORT:-19090}"
AM_PORT="${ONCALL_AM_PORT:-19093}"
GRAFANA_PORT="${ONCALL_GRAFANA_PORT:-13000}"
GATEWAY_PORT="${ONCALL_GATEWAY_PORT:-18080}"
CHANNEL_PORT="${ONCALL_CHANNEL_PORT:-18090}"
K6_JOB="oncall-k6"
K6_CONFIGMAP="oncall-k6-script"
PG_DEPLOY="oncall-postgres"
FIX_INDEX="ix_documents_folder_id_updated_at"
export MONITORING_NS PLATFORM_NS PROM_SVC AM_SVC GRAFANA_SVC PROM_PORT AM_PORT GRAFANA_PORT
export GATEWAY_PORT CHANNEL_PORT K6_JOB K6_CONFIGMAP PG_DEPLOY FIX_INDEX

log()  { echo "[oncall] $*"; }
warn() { echo "[oncall] WARN: $*" >&2; }
die()  { echo "[oncall] ERROR: $*" >&2; exit 1; }

# Sets every KEY=value of vars.env that the environment has not already set.
load_vars() {
  local key value
  while IFS='=' read -r key value; do
    [[ "${key}" =~ ^[A-Z][A-Z0-9_]*$ ]] || continue
    if [ -z "${!key+x}" ]; then
      export "${key}=${value}"
    fi
  done <"${ONCALL_DIR}/vars.env"
}
load_vars
export CHANNEL_HOST="${CHANNEL_HOST:-incident.demo.otterworks.app}"

require_bins() {
  local b
  for b in "$@"; do
    command -v "${b}" >/dev/null 2>&1 || die "${b} is required"
  done
}

# Only the two demo tenants are valid targets. Anything else is refused so a
# typo can never seed or load another tenant.
require_tenant() {
  local t="${1:-}"
  [ -n "${t}" ] || die "a tenant is required (${BEFORE_TENANT} or ${AFTER_TENANT})"
  case "${t}" in
    "${BEFORE_TENANT}"|"${AFTER_TENANT}") ;;
    *) die "unknown tenant '${t}'; expected ${BEFORE_TENANT} or ${AFTER_TENANT}" ;;
  esac
}

# Tenants named on the command line, or both when none are given.
tenants_or_both() {
  if [ "$#" -gt 0 ]; then
    local t
    for t in "$@"; do require_tenant "${t}"; echo "${t}"; done
  else
    echo "${BEFORE_TENANT}"
    echo "${AFTER_TENANT}"
  fi
}

tenant_ns()     { echo "otterworks-$1"; }
tenant_branch() { echo "demo-$1"; }
api_host()      { echo "api-t-$1.demo.otterworks.app"; }
web_host()      { echo "t-$1.demo.otterworks.app"; }
now_iso()       { date -u +%Y-%m-%dT%H:%M:%SZ; }

ensure_kubeconfig() {
  require_bins kubectl
  if [ -z "${KUBERNETES_SERVICE_HOST:-}" ] && ! kubectl version --request-timeout=5s >/dev/null 2>&1; then
    require_bins aws
    aws eks update-kubeconfig --name otterworks-dev --region us-east-1 >/dev/null
  fi
}

require_ns() {
  kubectl get ns "$1" >/dev/null 2>&1 || die "namespace $1 not found; run make oncall-up first"
}

# wait_ready <tenant> <deployment...>
wait_ready() {
  local t="$1" ns d
  ns="$(tenant_ns "${t}")"
  shift
  for d in "$@"; do
    kubectl -n "${ns}" rollout status "deploy/${d}" --timeout=5m >/dev/null ||
      die "deploy/${d} did not become ready in ${ns}; kubectl -n ${ns} describe deploy/${d}"
  done
}

# wake_tenant <tenant> <deployment...>: idle-suspend scales a tenant without
# ingress traffic for an hour to zero, oncall-postgres included. Scale the whole
# tenant back up and wait for the named Deployments.
wake_tenant() {
  local t="$1"
  shift
  "${REPO}/scripts/tenant-scale.sh" "${t}" up >/dev/null ||
    die "scripts/tenant-scale.sh ${t} up failed"
  wait_ready "${t}" "$@"
}

# wake_postgres <tenant>: only the tenant Postgres, for the steps that need SQL
# and nothing else (disarm, reset).
wake_postgres() {
  local ns
  ns="$(tenant_ns "$1")"
  if [ "$(kubectl -n "${ns}" get deploy "${PG_DEPLOY}" -o jsonpath='{.spec.replicas}')" = 0 ]; then
    log "${ns}/${PG_DEPLOY} is scaled to zero (idle suspend); scaling it up"
    kubectl -n "${ns}" scale "deploy/${PG_DEPLOY}" --replicas=1 >/dev/null
  fi
  wait_ready "$1" "${PG_DEPLOY}"
}

# ---------- state: incident/oncall/.state/<tenant>.json ----------
state_file() { echo "${STATE_DIR}/$1.json"; }

state_init() {
  local t="$1" f
  f="$(state_file "${t}")"
  mkdir -p "${STATE_DIR}"
  [ -f "${f}" ] || jq -n --arg t "${t}" --arg ns "$(tenant_ns "${t}")" --arg run "${RUN_ID}" \
    '{tenant: $t, namespace: $ns, run_id: $run, steps: {}}' >"${f}"
}

# state_update <tenant> <jq filter> [jq args...]
state_update() {
  local t="$1" filter="$2" f tmp
  shift 2
  state_init "${t}"
  f="$(state_file "${t}")"
  tmp="$(mktemp "${STATE_DIR}/.tmp.XXXXXX")"
  jq "$@" "${filter}" "${f}" >"${tmp}" && mv "${tmp}" "${f}"
}

state_get() {
  local f
  f="$(state_file "$1")"
  [ -f "${f}" ] || return 0
  jq -r "$2 // empty" "${f}"
}

# ---------- port-forwards (fail closed, as in incident/tenant.sh) ----------
PF_PIDS=()
PF_PORTS=""
pf_cleanup() {
  local p
  for p in "${PF_PIDS[@]:-}"; do
    if [ -n "${p}" ]; then kill "${p}" 2>/dev/null || true; fi
  done
  PF_PIDS=()
  PF_PORTS=""
}
trap pf_cleanup EXIT

# pf_start <namespace> <svc/name> <local-port> <remote-port> <health-path>
pf_start() {
  local ns="$1" target="$2" lport="$3" rport="$4" path="$5" pid
  case " ${PF_PORTS} " in *" ${lport} "*) return 0 ;; esac
  if curl --connect-timeout 2 --max-time 5 -s -o /dev/null "http://localhost:${lport}${path}" 2>/dev/null; then
    die "localhost:${lport} is already serving something; pick a free port with the ONCALL_*_PORT variables"
  fi
  kubectl -n "${ns}" port-forward "${target}" "${lport}:${rport}" >/dev/null 2>&1 &
  pid=$!
  PF_PIDS+=("${pid}")
  PF_PORTS+=" ${lport}"
  for _ in $(seq 1 75); do
    kill -0 "${pid}" 2>/dev/null || die "port-forward to ${ns}/${target} exited"
    curl --max-time 2 -s -o /dev/null "http://localhost:${lport}${path}" 2>/dev/null && return 0
    sleep 0.2
  done
  die "port-forward to ${ns}/${target} never answered on ${path}"
}

pf_prometheus()   { pf_start "${MONITORING_NS}" "svc/${PROM_SVC}" "${PROM_PORT}" 9090 /-/ready; }
pf_alertmanager() { pf_start "${MONITORING_NS}" "svc/${AM_SVC}" "${AM_PORT}" 9093 /-/ready; }
pf_grafana()      { pf_start "${MONITORING_NS}" "svc/${GRAFANA_SVC}" "${GRAFANA_PORT}" 80 /api/health; }

# prom_query <promql>: prints the JSON result vector.
prom_query() {
  curl -fsS --max-time 20 "http://localhost:${PROM_PORT}/api/v1/query" \
    --data-urlencode "query=$1" | jq -c '.data.result'
}

# prom_scalar_at <promql> <unix seconds>: first sample value at that instant,
# empty when the query returns nothing.
prom_scalar_at() {
  curl -fsS --max-time 20 "http://localhost:${PROM_PORT}/api/v1/query" \
    --data-urlencode "query=$1" --data-urlencode "time=$2" | jq -r '.data.result[0].value[1] // empty'
}

# ---------- secrets (values stay in variables, never echoed) ----------
# secret_value <namespace> <secret> <key>; empty output when absent.
secret_value() {
  local raw
  raw="$(kubectl -n "$1" get secret "$2" -o jsonpath="{.data.$3}" 2>/dev/null)" || return 0
  [ -n "${raw}" ] || return 0
  printf '%s' "${raw}" | base64 -d
}

# ---------- tenant Postgres ----------
# pg <tenant> [psql args...]: runs psql over the pod's local socket (trust auth
# inside the container), so no password crosses kubectl.
pg() {
  local ns
  ns="$(tenant_ns "$1")"
  shift
  kubectl -n "${ns}" exec -i "deploy/${PG_DEPLOY}" -c postgres -- \
    psql -U otterworks -d otterworks -v ON_ERROR_STOP=1 -X -q "$@"
}

# ---------- alembic ----------
# branch_alembic_head <git ref>: newest document-service migration on that ref.
branch_alembic_head() {
  git -C "${REPO}" ls-tree --name-only "$1" services/document-service/alembic/versions/ |
    sed -nE 's#.*/([0-9]{3})_[^/]*\.py$#\1#p' | sort | tail -n 1
}

# db_alembic_revision <tenant>: the revision stamped in the tenant Postgres,
# empty before document-service first migrated it.
db_alembic_revision() {
  [ "$(pg "$1" -At -c "SELECT to_regclass('public.alembic_version') IS NOT NULL")" = t ] || return 0
  pg "$1" -At -c 'SELECT version_num FROM alembic_version LIMIT 1'
}

# require_db_shipped <tenant>: document-service runs `alembic upgrade head` on
# start, so a pod of the tenant branch's image crash-loops when the database is
# stamped with a revision that branch does not ship (migration 005 applied from
# an unmerged fix branch). Refuse any rollout in that state.
require_db_shipped() {
  local t="$1" branch head current
  branch="$(tenant_branch "${t}")"
  if ! git -C "${REPO}" fetch -q origin "+refs/heads/${branch}:refs/remotes/origin/${branch}" 2>/dev/null; then
    warn "could not fetch ${branch}; skipping the alembic revision check"
    return 0
  fi
  head="$(branch_alembic_head "origin/${branch}")"
  current="$(db_alembic_revision "${t}")"
  if [ -n "${head}" ] && [ -n "${current}" ] && [[ "${current}" > "${head}" ]]; then
    die "$(tenant_ns "${t}") Postgres is at alembic revision ${current}, but ${branch} ships up to ${head}; a document-service rollout would crash-loop. Run alembic downgrade ${head} from the fix branch first (.agents/skills/oncall-storm/SKILL.md)"
  fi
}

# ---------- document-service release ----------
helm_revision() {
  helm -n "$(tenant_ns "$1")" history document-service -o json 2>/dev/null | jq -r 'last.revision // empty'
}

digest_enabled() {
  helm -n "$(tenant_ns "$1")" get values document-service -o json 2>/dev/null |
    jq -r '.folderDigest.enabled // false'
}

# cluster_deploy_record <tenant>: the arm's config deploy as Helm recorded it,
# for a checkout that did not run arm.sh. Prints {at, oncall_run, revision} for
# the oldest revision in the unbroken run of revisions, ending at the deployed
# one, whose values carry the live oncall_run; at is that revision's Helm
# update time. Prints nothing when the worker is off or no oncall_run is set.
cluster_deploy_record() {
  local ns values run history current first r updated
  ns="$(tenant_ns "$1")"
  values="$(helm -n "${ns}" get values document-service -o json 2>/dev/null)" || return 0
  run="$(jq -r '.monitoring.rules.extraLabels.oncall_run // empty' <<<"${values}")"
  [ -n "${run}" ] || return 0
  [ "$(jq -r '.folderDigest.enabled // false' <<<"${values}")" = true ] || return 0
  history="$(helm -n "${ns}" history document-service --max 50 -o json 2>/dev/null)" || return 0
  current="$(jq -r '[.[] | select(.status == "deployed")] | last.revision // empty' <<<"${history}")"
  [ -n "${current}" ] || return 0
  first="${current}"
  for r in $(jq -r --argjson c "${current}" '[.[] | select(.revision < $c) | .revision] | reverse | .[]' <<<"${history}"); do
    [ "$(helm -n "${ns}" get values document-service --revision "${r}" -o json 2>/dev/null |
      jq -r '.monitoring.rules.extraLabels.oncall_run // empty')" = "${run}" ] || break
    first="${r}"
  done
  updated="$(jq -r --argjson r "${first}" '.[] | select(.revision == $r) | .updated' <<<"${history}")"
  [ -n "${updated}" ] || return 0
  jq -nc --arg at "$(date -u -d "${updated}" +%Y-%m-%dT%H:%M:%SZ)" --arg run "${run}" --argjson rev "${first}" \
    '{at: $at, oncall_run: $run, revision: $rev}'
}

# start_load <tenant>: (re)start the oncall-k6 Job against the seeded owner and
# record it in .state. A running Job is replaced, so the run starts now.
start_load() {
  local t="$1" ns owner
  ns="$(tenant_ns "${t}")"
  owner="$(state_get "${t}" .owner_id)"
  [ -n "${owner}" ] || owner="$(pg "${t}" -At -c "SELECT owner_id FROM documents LIMIT 1")"
  [ -n "${owner}" ] || die "no seeded documents in ${ns}; run make oncall-arm TENANT=${t} first"
  kubectl -n "${ns}" create configmap "${K6_CONFIGMAP}" \
    --from-file=folders.js="${ONCALL_DIR}/k6/folders.js" --dry-run=client -o yaml |
    kubectl -n "${ns}" apply -f - >/dev/null
  kubectl -n "${ns}" delete job "${K6_JOB}" --ignore-not-found --wait=true >/dev/null
  K6_DEADLINE_SECONDS="$(awk -v m="${LOAD_MINUTES}" 'BEGIN { printf "%d", m * 60 + 600 }')"
  TENANT="${t}" API_HOST="$(api_host "${t}")" OWNER_ID="${owner}" \
    K6_DEADLINE_SECONDS="${K6_DEADLINE_SECONDS}" \
    render "${ONCALL_DIR}/k8s/k6-job.yaml" RUN_ID K6_DEADLINE_SECONDS API_HOST TENANT OWNER_ID \
      DEMO_USER_EMAIL SEED_FOLDERS LOAD_VUS LOAD_MINUTES P95_SLO_SECONDS |
    kubectl -n "${ns}" apply -f - >/dev/null
  kubectl -n "${ns}" wait --for=condition=Ready pod -l app=oncall-k6 --timeout=3m >/dev/null ||
    die "the ${K6_JOB} pod did not start in ${ns}; kubectl -n ${ns} describe job ${K6_JOB}"
  # shellcheck disable=SC2016 # jq filter
  state_update "${t}" \
    '.steps.load = {at: $at, job: $job, vus: $vus, minutes: $min, url: $url}' \
    --arg at "$(now_iso)" --arg job "${K6_JOB}" --arg url "https://$(api_host "${t}")" \
    --argjson vus "${LOAD_VUS}" --argjson min "${LOAD_MINUTES}"
}

# The harness turns chart keys on and off; it never adds them. Refuse to run
# against a chart that does not have them yet.
require_chart_keys() {
  local values
  values="$(helm show values "${CHART_DIR}")"
  printf '%s\n' "${values}" | grep -q '^folderDigest:' ||
    die "document-service chart has no folderDigest values; this checkout predates the on-call chart changes"
  printf '%s\n' "${values}" | grep -q '^database:' ||
    die "document-service chart has no database values; this checkout predates the on-call chart changes"
}

# digest_deploy <tenant> true|false [oncall_run]: one Helm revision that flips
# the worker. oncall_run is stamped on every storm alert, so each arm gets new
# alert fingerprints under the same Alertmanager group key; an empty value
# removes the label.
digest_deploy() {
  local t="$1" enabled="$2" run="${3:-}" ns
  ns="$(tenant_ns "${t}")"
  require_chart_keys
  require_db_shipped "${t}"
  helm -n "${ns}" upgrade document-service "${CHART_DIR}" --reuse-values \
    --set "folderDigest.enabled=${enabled}" \
    --set-string "monitoring.rules.extraLabels.oncall_run=${run}" \
    --set "folderDigest.intervalSeconds=${DIGEST_INTERVAL_SECONDS}" \
    --set "folderDigest.concurrency=${DIGEST_CONCURRENCY}" \
    --set "database.statementTimeoutMs=${STATEMENT_TIMEOUT_MS}" \
    --set "database.poolSize=${DB_POOL_SIZE}" \
    --set "database.maxOverflow=${DB_MAX_OVERFLOW}" \
    --wait --timeout 6m >/dev/null
  kubectl -n "${ns}" rollout status deploy/document-service --timeout=5m >/dev/null
}

# ---------- Alertmanager ----------
# am_reload: rebuilds the dispatcher, which drops every aggregation group held
# in memory. The notification log survives, so a group whose firing alerts did
# not change since its last page is not notified again; a group that gained
# alerts since then is, so only reload when this tenant needs it
# (oncall_group_may_linger).
am_reload() {
  pf_alertmanager
  curl -fsS --max-time 20 -X POST -o /dev/null "http://localhost:${AM_PORT}/-/reload" ||
    die "Alertmanager did not accept POST /-/reload"
}

# am_route_seconds <receiver> <group_wait|group_interval>: that timer of the
# receiver's route in the live Alertmanager config, in seconds; empty when the
# route is absent.
am_route_seconds() {
  curl -fsS --max-time 20 "http://localhost:${AM_PORT}/api/v2/status" | jq -r '.config.original' |
    python3 -c 'import re, sys, yaml
receiver, key = sys.argv[1], sys.argv[2]
defaults = {"group_wait": "30s", "group_interval": "5m"}
units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "y": 31536000}
def seconds(text):
    parts = re.findall(r"(\d+)(ms|[smhdwy])", str(text))
    return int(sum(int(n) * units[u] for n, u in parts))
def walk(route, inherited):
    for child in route.get("routes") or []:
        value = child.get(key, inherited)
        if child.get("receiver") == receiver:
            return value
        found = walk(child, value)
        if found is not None:
            return found
    return None
root = yaml.safe_load(sys.stdin).get("route") or {}
value = walk(root, root.get(key, defaults[key]))
print("" if value is None else seconds(value))' "$1" "$2"
}

# oncall_group_may_linger <namespace> [unix seconds]: true when a page="oncall"
# alert fired in the namespace within the oncall-devin group_interval before
# that instant (default now). Alertmanager keeps that group, resolved alerts
# included, until its next flush, and a new storm would join it and wait for
# that flush instead of paging after group_wait. The groups API hides resolved
# alerts, so ask Prometheus. Needs both port-forwards.
oncall_group_may_linger() {
  local ns="$1" at="${2:-$(date +%s)}" interval n
  interval="$(am_route_seconds oncall-devin group_interval)"
  [ -n "${interval}" ] || return 1
  n="$(prom_scalar_at "count(last_over_time(ALERTS{namespace=\"${ns}\",page=\"oncall\",alertstate=\"firing\"}[${interval}s]))" "${at}")"
  [ "${n:-0}" -ge 1 ]
}

# am_reloaded_between <from> <to>: the latest Alertmanager config reload in
# [from, to] (unix seconds) as ISO time, empty when there was none. Looks up to
# 5 minutes past <to> so a reload just before a deploy is seen even though
# Prometheus scraped it later. Needs the Prometheus port-forward.
am_reloaded_between() {
  local from="$1" to="$2" at window ts
  at=$(( to + 300 ))
  [ "${at}" -le "$(date +%s)" ] || at="$(date +%s)"
  window=$(( at - from + 60 ))
  ts="$(prom_scalar_at "max(max_over_time((alertmanager_config_last_reload_success_timestamp_seconds <= ${to})[${window}s:15s]))" "${at}")"
  [ -n "${ts}" ] || return 0
  ts="${ts%.*}"
  [ "${ts}" -ge "${from}" ] || return 0
  date -u -d "@${ts}" +%Y-%m-%dT%H:%M:%SZ
}

# grafana_annotate <tenant> <text>: sets ANNOTATION_ID (empty when Grafana
# refused). A global rather than stdout, so the port-forward is started by this
# shell and cleaned up by its EXIT trap.
ANNOTATION_ID=""
grafana_annotate() {
  local t="$1" text="$2" ns user pass body uid
  ANNOTATION_ID=""
  ns="$(tenant_ns "${t}")"
  user="$(secret_value "${MONITORING_NS}" grafana-admin admin-user)"
  pass="$(secret_value "${MONITORING_NS}" grafana-admin admin-password)"
  if [ -z "${user}" ] || [ -z "${pass}" ]; then
    warn "grafana-admin secret not readable; no annotation"
    return 0
  fi
  pf_grafana
  # Dashboard-scoped first so it shows on oncall-storm; org-wide if that uid
  # is not provisioned yet.
  for uid in oncall-storm ""; do
    body="$(jq -nc --arg text "${text}" --arg ns "${ns}" --arg uid "${uid}" \
      --argjson time "$(($(date +%s) * 1000))" \
      '{time: $time, text: $text, tags: ["oncall-storm", "deploy", "document-service", $ns]}
       + (if $uid == "" then {} else {dashboardUID: $uid} end)')"
    ANNOTATION_ID="$(printf 'user = "%s:%s"\n' "${user}" "${pass}" |
      curl -fsS --max-time 10 --config - -H 'Content-Type: application/json' \
        --data "${body}" "http://localhost:${GRAFANA_PORT}/api/annotations" 2>/dev/null |
      jq -r '.id // empty')" || ANNOTATION_ID=""
    [ -n "${ANNOTATION_ID}" ] && return 0
  done
  warn "Grafana did not accept the annotation"
}

# render <file> VAR...: envsubst limited to the named variables.
render() {
  local file="$1" spec="" v
  shift
  for v in "$@"; do spec+="\${${v}} "; done
  envsubst "${spec}" <"${file}"
}
