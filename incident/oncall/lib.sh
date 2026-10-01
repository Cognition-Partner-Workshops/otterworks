#!/usr/bin/env bash
# Shared helpers for the on-call alert storm harness. Sourced, never executed.
# Conventions follow incident/tenant.sh and scripts/lib/tenant-common.sh:
# namespace-per-tenant, fail-closed port-forwards, secrets read from Kubernetes
# and passed by stdin or environment, never on argv and never printed.

ONCALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${ONCALL_DIR}/../.." && pwd)"
STATE_DIR="${ONCALL_DIR}/.state"
REPORT_DIR="${ONCALL_DIR}/reports"
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

# ---------- document-service release ----------
helm_revision() {
  helm -n "$(tenant_ns "$1")" history document-service -o json 2>/dev/null | jq -r 'last.revision // empty'
}

digest_enabled() {
  helm -n "$(tenant_ns "$1")" get values document-service -o json 2>/dev/null |
    jq -r '.folderDigest.enabled // false'
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
# in memory. The notification log survives, so groups whose alerts did not
# change are not notified again. Without this, a storm armed within
# group_interval (6h) of the previous page joins that group and waits for its
# next flush instead of paging after group_wait.
am_reload() {
  pf_alertmanager
  curl -fsS --max-time 20 -X POST -o /dev/null "http://localhost:${AM_PORT}/-/reload" ||
    die "Alertmanager did not accept POST /-/reload"
}

# am_group_wait_seconds <receiver>: group_wait of that receiver's route in the
# live Alertmanager config, in seconds; empty when the route is absent.
am_group_wait_seconds() {
  curl -fsS --max-time 20 "http://localhost:${AM_PORT}/api/v2/status" | jq -r '.config.original' |
    python3 -c 'import re, sys, yaml
receiver = sys.argv[1]
units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "y": 31536000}
def seconds(text):
    parts = re.findall(r"(\d+)(ms|[smhdwy])", str(text))
    return int(sum(int(n) * units[u] for n, u in parts))
def walk(route, inherited):
    for child in route.get("routes") or []:
        wait = child.get("group_wait", inherited)
        if child.get("receiver") == receiver:
            return wait
        found = walk(child, wait)
        if found is not None:
            return found
    return None
root = yaml.safe_load(sys.stdin).get("route") or {}
wait = walk(root, root.get("group_wait", "30s"))
print("" if wait is None else seconds(wait))' "$1"
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
