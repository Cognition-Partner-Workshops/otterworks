#!/usr/bin/env bash
# Two live legacy-portal endpoints on this host, for parity rehearsals: the Java portal on its own
# PostgreSQL, and the real Lambda handlers (Lambda RIE) behind a local HTTP API with a local RDS Data
# API on a second PostgreSQL. Nothing leaves the host; no cloud credentials are read or needed.
#
#   RUN_TOKEN=<token> scripts/lp-local.sh up|identity|replay|reset [ctx]|state <java|lambda> <ctx>|down|verify-clean
#
# RUN_TOKEN labels every container, image, network and volume (compose project = lp_<lowercased token>).
# LP_JAVA_PORT (18095) and LP_LAMBDA_PORT (18096) pick the loopback ports. replay takes CTX
# (default all), STAGE (first|full, default full) and OUT (default services/legacy-portal/parity/out-live).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT}/services/legacy-portal-lambda/local/docker-compose.yml"
PARITY="${ROOT}/services/legacy-portal/parity"
export LP_JAVA_PORT="${LP_JAVA_PORT:-18095}" LP_LAMBDA_PORT="${LP_LAMBDA_PORT:-18096}"

die() { echo "lp-local: $*" >&2; exit 2; }
[ -n "${RUN_TOKEN:-}" ] || die "RUN_TOKEN is required, e.g. RUN_TOKEN=LP_$(date -u +%Y%m%d)"
[[ "$RUN_TOKEN" =~ ^[A-Za-z0-9_]{3,40}$ ]] || die "RUN_TOKEN must be 3-40 letters, digits or underscores"
export RUN_TOKEN
PROJECT="lp_$(echo "$RUN_TOKEN" | tr '[:upper:]' '[:lower:]')"
dc() { docker compose -p "$PROJECT" -f "$COMPOSE_FILE" "$@"; }

tables_for() {
  case "$1" in
    announcements) echo "announcements.announcement" ;;
    preferences|user_preferences) echo "user_preferences.user_preference" ;;
    feedback) echo "feedback.feedback" ;;
    common) echo "" ;;
    all) echo "announcements.announcement user_preferences.user_preference feedback.feedback" ;;
    *) die "context must be common, announcements, preferences, feedback or all, got $1" ;;
  esac
}

psql_in() { dc exec -T "$1" psql -U legacyportal -d legacyportal -v ON_ERROR_STOP=1 -qAt -c "$2"; }

wait_http() {
  local url="$1" i
  for i in $(seq 1 90); do
    curl -fsS -o /dev/null "$url" 2>/dev/null && return 0
    sleep 2
  done
  die "timed out waiting for $url"
}

cmd_up() {
  dc up -d --build --wait java-db lambda-db
  dc exec -T lambda-db psql -U legacyportal -d legacyportal -v ON_ERROR_STOP=1 -q \
    -f /docker-entrypoint-initdb.d/zz-dataapi-role.sql
  dc run --rm --no-deps -T certs
  dc up -d --build
  dc restart dataapi
  wait_http "http://127.0.0.1:${LP_JAVA_PORT}/health"
  wait_http "http://127.0.0.1:${LP_LAMBDA_PORT}/health"
  cmd_reset all
  cmd_identity
}

# Truncate the context's tables and restart their sequences in both stores. The Java app keeps no
# store state in memory; the Lambda functions are restarted so each context starts from cold handlers.
cmd_reset() {
  local ctx="${1:-${CTX:-all}}" tables sql
  tables="$(tables_for "$ctx")"
  [ -n "$tables" ] || { echo "reset ${ctx}: no tables"; return 0; }
  sql="TRUNCATE ${tables// /, } RESTART IDENTITY"
  local java_pid lambda_pid
  psql_in java-db "$sql" & java_pid=$!
  psql_in lambda-db "$sql" & lambda_pid=$!
  wait "$java_pid" || die "reset ${ctx}: truncate failed in java-db"
  wait "$lambda_pid" || die "reset ${ctx}: truncate failed in lambda-db"
  local fns
  case "$ctx" in
    all) fns="fn-announcements fn-preferences fn-feedback" ;;
    preferences|user_preferences) fns="fn-preferences" ;;
    *) fns="fn-${ctx}" ;;
  esac
  # shellcheck disable=SC2086
  dc restart $fns >/dev/null 2>&1
  echo "reset ${ctx}: truncated ${tables} in java-db and lambda-db; restarted ${fns}" >&2
}

cmd_state() {
  local store="${1:?store java|lambda}" ctx="${2:?context}" t parts=()
  case "$store" in java) store=java-db ;; lambda) store=lambda-db ;; *) die "store must be java or lambda" ;; esac
  for t in $(tables_for "$ctx"); do
    parts+=("'${t}', coalesce((select json_agg(r) from ${t} r), '[]'::json)")
  done
  [ ${#parts[@]} -gt 0 ] || { echo '{}'; return 0; }
  local args
  args="$(printf '%s,' "${parts[@]}")"
  psql_in "$store" "select json_build_object(${args%,})"
}

cmd_identity() {
  echo "java   http://127.0.0.1:${LP_JAVA_PORT}  $(curl -fsS "http://127.0.0.1:${LP_JAVA_PORT}/health")"
  echo "lambda http://127.0.0.1:${LP_LAMBDA_PORT}  $(curl -fsS "http://127.0.0.1:${LP_LAMBDA_PORT}/__lp_local/identity")"
  docker ps --filter "label=run_token=${RUN_TOKEN}" --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
}

# The endpoints replayed must be the ones this run published, or resets and snapshots (by project)
# would check stores other than the ones the requests changed.
check_ports() {
  local java lambda
  java="$(dc port java 8095 2>/dev/null || true)" lambda="$(dc port gateway 8080 2>/dev/null || true)"
  [ "$java" = "127.0.0.1:${LP_JAVA_PORT}" ] && [ "$lambda" = "127.0.0.1:${LP_LAMBDA_PORT}" ] || \
    die "run ${RUN_TOKEN} publishes java='${java:-none}' lambda='${lambda:-none}', not 127.0.0.1:${LP_JAVA_PORT}/${LP_LAMBDA_PORT}; set LP_JAVA_PORT/LP_LAMBDA_PORT to match"
}

cmd_replay() {
  local ctx="${CTX:-all}" ctx_args=() c self
  for c in ${ctx//,/ }; do ctx_args+=(--context "$c"); done
  check_ports
  self="$(printf '%q' "${ROOT}/scripts/lp-local.sh")"
  python3 "${PARITY}/live_parity.py" \
    --java-base "http://127.0.0.1:${LP_JAVA_PORT}" --lambda-base "http://127.0.0.1:${LP_LAMBDA_PORT}" \
    --reset-cmd "${self} reset {context}" \
    --state-cmd "${self} state {store} {context}" \
    --fixture-file "${ROOT}/services/legacy-portal/scripts/initdb.sql" \
    --fixture-file "${ROOT}/infrastructure/terraform/legacy-portal-serverless/schema.sql" \
    --run-token "$RUN_TOKEN" --stage "${STAGE:-full}" --out "${OUT:-${PARITY}/out-live}" "${ctx_args[@]}"
}

cmd_down() {
  dc down -v --remove-orphans --rmi local
  docker image ls --filter "label=run_token=${RUN_TOKEN}" -q | sort -u | xargs -r docker image rm -f >/dev/null
}

cmd_verify_clean() {
  local left=0 kind out
  for kind in container volume network image; do
    case "$kind" in
      container) out="$(docker ps -a --filter "label=run_token=${RUN_TOKEN}" --format '{{.Names}}'; \
                        docker ps -a --filter "label=com.docker.compose.project=${PROJECT}" --format '{{.Names}}')" ;;
      volume) out="$(docker volume ls --filter "label=run_token=${RUN_TOKEN}" -q; docker volume ls -q | grep -i "^${PROJECT}_" || true)" ;;
      network) out="$(docker network ls --filter "label=run_token=${RUN_TOKEN}" --format '{{.Name}}'; \
                      docker network ls --format '{{.Name}}' | grep -i "^${PROJECT}_" || true)" ;;
      image) out="$(docker image ls --filter "label=run_token=${RUN_TOKEN}" --format '{{.Repository}}:{{.Tag}}'; \
                    docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -i ":${RUN_TOKEN}$" || true)" ;;
    esac
    out="$(echo "$out" | sed '/^$/d' | sort -u)"
    if [ -n "$out" ]; then left=1; echo "remaining ${kind}s for ${RUN_TOKEN}:"; echo "$out" | sed 's/^/  /'
    else echo "${kind}s labelled or named ${RUN_TOKEN}: none"; fi
  done
  [ "$left" -eq 0 ] && echo "verify-clean ${RUN_TOKEN}: clean" || { echo "verify-clean ${RUN_TOKEN}: NOT clean"; exit 1; }
}

case "${1:-}" in
  up) cmd_up ;;
  identity) cmd_identity ;;
  replay) cmd_replay ;;
  reset) cmd_reset "${2:-}" ;;
  state) cmd_state "${2:-}" "${3:-}" ;;
  down) cmd_down ;;
  verify-clean) cmd_verify_clean ;;
  *) die "usage: RUN_TOKEN=<token> $0 up|identity|replay|reset [ctx]|state <java|lambda> <ctx>|down|verify-clean" ;;
esac
