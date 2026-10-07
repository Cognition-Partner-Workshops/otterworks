#!/usr/bin/env bash
# Compose smoke test for the search service (run from anywhere; uses the repo root).
#
#   services/search-service/scripts/compose_smoke.sh      # or: make search-smoke
#
# Brings up redis, meilisearch and localstack, waits for the SQS queue, then
# builds and starts search-service (default image: uvicorn, 2 workers) and
# checks health/readiness, the four search_service_* metric families,
# index -> search -> owner isolation -> delete, 401 without credentials, the
# planted suggest_500 chaos flag (set -> 500, cleared -> 200) and the
# structured JSON log events. Tears the stack down on exit and exits non-zero
# on the first failure.
#
# /metrics is per process and the image runs two workers, so the metrics
# check is presence-only (HELP/TYPE lines are emitted by every worker).
#
# Environment:
#   SMOKE_LOG_DIR       where compose_smoke.log and search-service.log go
#                       (default: $TMPDIR/search-smoke)
#   SMOKE_IMAGE_MIRROR  registry to pre-pull Docker Hub images from and retag,
#                       e.g. mirror.gcr.io (default: unset, pull as usual)
#   SMOKE_KEEP=1        leave the stack running after the run
#   SMOKE_TIMEOUT       seconds to wait for health / indexing (default: 120)
#   COMPOSE_PROJECT_NAME  default: otterworks-search-smoke (its volumes are
#                       removed on teardown)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-otterworks-search-smoke}"
LOG_DIR="${SMOKE_LOG_DIR:-${TMPDIR:-/tmp}/search-smoke}"
TIMEOUT="${SMOKE_TIMEOUT:-120}"
BASE_URL="http://localhost:8087"
SEARCH="$BASE_URL/api/v1/search"
CONTAINER="otterworks-search-service"
CHAOS_KEY="chaos:search-service:suggest_500"
BACKING=(redis meilisearch localstack)
SQS_QUEUE="otterworks-search-events"
COMPOSE=(docker compose -f docker-compose.infra.yml -f docker-compose.yml)

RUN_ID="smoke-$(date +%s)-$$"
OWNER="smoke-owner-$RUN_ID"
OTHER="smoke-other-$RUN_ID"
DOC_ID="smoke-doc-$RUN_ID"
TERM_="smokeotter${RUN_ID//[^0-9]/}"

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/compose_smoke.log"
CONTAINER_LOG="$LOG_DIR/search-service.log"
: >"$LOG"
exec > >(tee -a "$LOG") 2>&1

PASSED=0
log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
pass() { PASSED=$((PASSED + 1)); log "PASS  $*"; }
fail() { log "FAIL  $*"; exit 1; }

teardown() {
  local rc=$?
  set +e
  "${COMPOSE[@]}" logs --no-color --no-log-prefix search-service >"$CONTAINER_LOG" 2>&1
  if [[ $rc -ne 0 ]]; then
    log "--- docker compose ps ---"
    "${COMPOSE[@]}" ps
    log "--- search-service logs (last 80 lines) ---"
    tail -n 80 "$CONTAINER_LOG"
  fi
  if [[ "${SMOKE_KEEP:-0}" == "1" ]]; then
    log "SMOKE_KEEP=1: leaving project $COMPOSE_PROJECT_NAME running"
  else
    log "tearing down project $COMPOSE_PROJECT_NAME"
    "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1
  fi
  if [[ $rc -eq 0 ]]; then
    log "RESULT: PASS ($PASSED checks)"
  else
    log "RESULT: FAIL (exit $rc after $PASSED passing checks)"
  fi
  log "logs: $LOG, $CONTAINER_LOG"
  exit "$rc"
}
trap teardown EXIT

# http METHOD URL [curl args...] -> sets STATUS and BODY
http() {
  local method=$1 url=$2
  shift 2
  local out
  out=$(curl -sS -o - -w '\n%{http_code}' -X "$method" "$@" "$url") || fail "curl $method $url"
  STATUS=${out##*$'\n'}
  BODY=${out%$'\n'*}
}

expect_status() {
  local want=$1 what=$2
  [[ "$STATUS" == "$want" ]] || fail "$what: want HTTP $want, got $STATUS: $BODY"
}

json() { python3 -c "import json,sys; d=json.load(sys.stdin); print($1)" <<<"$BODY"; }

redis_cli() { "${COMPOSE[@]}" exec -T redis redis-cli "$@"; }

pull_from_mirror() {
  local mirror=$1 img src
  local images=("$(sed -n 's/^FROM[[:space:]]\+\([^[:space:]]\+\).*/\1/p' services/search-service/Dockerfile | head -n1)")
  mapfile -t -O 1 images < <("${COMPOSE[@]}" config --images redis meilisearch localstack)
  for img in "${images[@]}"; do
    src=$img
    [[ "${img%%/*}" == "$img" ]] && src="library/$img"
    log "pull $mirror/$src -> $img"
    docker pull -q "$mirror/$src" >/dev/null && docker tag "$mirror/$src" "$img"
  done
}

log "search-service compose smoke test; project=$COMPOSE_PROJECT_NAME run=$RUN_ID"
log "git: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

# 1. up --build and wait for the container healthcheck
if [[ -n "${SMOKE_IMAGE_MIRROR:-}" ]]; then
  pull_from_mirror "$SMOKE_IMAGE_MIRROR"
fi
# search-service only depends_on meilisearch; start the backing services first
# and wait for localstack's init hook to create the SQS queue so the consumer
# started in the lifespan does not race it.
log "docker compose up -d --wait ${BACKING[*]}"
"${COMPOSE[@]}" up -d --wait --wait-timeout "$TIMEOUT" "${BACKING[@]}"
deadline=$((SECONDS + TIMEOUT))
until "${COMPOSE[@]}" exec -T localstack awslocal sqs get-queue-url --queue-name "$SQS_QUEUE" >/dev/null 2>&1; do
  ((SECONDS < deadline)) || fail "SQS queue $SQS_QUEUE not created by localstack init after ${TIMEOUT}s"
  sleep 2
done
log "localstack SQS queue $SQS_QUEUE exists"
log "docker compose up -d --build search-service"
"${COMPOSE[@]}" up -d --build search-service

log "image CMD: $(docker inspect -f '{{json .Config.Cmd}}' "$CONTAINER")"
deadline=$((SECONDS + TIMEOUT))
until [[ "$(docker inspect -f '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null)" == "healthy" ]]; do
  ((SECONDS < deadline)) || fail "$CONTAINER not healthy after ${TIMEOUT}s ($(docker inspect -f '{{.State.Health.Status}}' "$CONTAINER" 2>&1))"
  sleep 2
done
pass "1 container healthcheck: $CONTAINER healthy"

# 2. health, readiness, metrics families
http GET "$BASE_URL/health"
expect_status 200 "/health"
[[ "$(json 'd["status"]')" == "alive" ]] || fail "/health body: $BODY"
pass "2 GET /health -> 200 $BODY"

deadline=$((SECONDS + TIMEOUT))
while http GET "$BASE_URL/health/ready"; [[ "$STATUS" != "200" ]]; do
  ((SECONDS < deadline)) || fail "/health/ready: want 200, got $STATUS: $BODY"
  sleep 2
done
[[ "$(json 'd["ready"]')" == "True" ]] || fail "/health/ready body: $BODY"
pass "2 GET /health/ready -> 200 $BODY"

http GET "$BASE_URL/metrics"
expect_status 200 "/metrics"
for family in search_service_requests_total search_service_request_duration_seconds \
  search_service_searches_total search_service_index_operations_total; do
  grep -qE "^# TYPE ${family%_total}(_total)? " <<<"$BODY" || fail "/metrics: family $family missing"
done
pass "2 GET /metrics -> 200 with all four search_service_* families"

# 3. index -> search -> owner isolation -> delete
doc=$(printf '{"id":"%s","title":"Smoke %s report","content":"Compose smoke test document %s","owner_id":"%s","tags":["smoke"]}' \
  "$DOC_ID" "$TERM_" "$TERM_" "$OWNER")
http POST "$SEARCH/index/document" -H "X-User-ID: $OWNER" -H "Content-Type: application/json" -d "$doc"
expect_status 201 "POST /index/document"
pass "3 POST /api/v1/search/index/document -> 201 $BODY"

deadline=$((SECONDS + TIMEOUT))
while :; do
  http GET "$SEARCH/?q=$TERM_" -H "X-User-ID: $OWNER"
  expect_status 200 "GET /api/v1/search/ (owner)"
  [[ "$(json 'any(r["id"] == "'"$DOC_ID"'" for r in d["results"])')" == "True" ]] && break
  ((SECONDS < deadline)) || fail "owner search never returned $DOC_ID: $BODY"
  sleep 1
done
pass "3 owner search finds $DOC_ID (total=$(json 'd["total"]'))"

http GET "$SEARCH/?q=$TERM_" -H "X-User-ID: $OTHER"
expect_status 200 "GET /api/v1/search/ (other user)"
[[ "$(json 'd["total"]')" == "0" ]] || fail "other X-User-ID can see the document: $BODY"
pass "3 other X-User-ID search -> 200 total=0"

http DELETE "$SEARCH/index/document/$DOC_ID" -H "X-User-ID: $OWNER"
expect_status 200 "DELETE /index/document/$DOC_ID"
pass "3 DELETE /api/v1/search/index/document/$DOC_ID -> 200 $BODY"

deadline=$((SECONDS + TIMEOUT))
while :; do
  http GET "$SEARCH/?q=$TERM_" -H "X-User-ID: $OWNER"
  expect_status 200 "GET /api/v1/search/ (after delete)"
  [[ "$(json 'd["total"]')" == "0" ]] && break
  ((SECONDS < deadline)) || fail "document still searchable after delete: $BODY"
  sleep 1
done
pass "3 owner search after delete -> total=0"

# 4. no credentials -> 401
http GET "$SEARCH/?q=$TERM_"
expect_status 401 "GET /api/v1/search/ without credentials"
[[ "$(json 'd["error"]')" == "unauthorized" ]] || fail "401 body: $BODY"
pass "4 GET /api/v1/search/ without credentials -> 401 $BODY"

# 5. planted chaos flag: set -> 500, cleared -> 200 (both workers read Redis per request)
redis_cli SET "$CHAOS_KEY" 1 >/dev/null
for _ in 1 2 3 4; do
  http GET "$SEARCH/suggest?q=smo" -H "X-User-ID: $OWNER"
  expect_status 500 "/suggest with $CHAOS_KEY set"
done
pass "5 $CHAOS_KEY set -> GET /suggest 500 (x4)"
redis_cli DEL "$CHAOS_KEY" >/dev/null
for _ in 1 2 3 4; do
  http GET "$SEARCH/suggest?q=smo" -H "X-User-ID: $OWNER"
  expect_status 200 "/suggest with $CHAOS_KEY cleared"
done
pass "5 $CHAOS_KEY cleared -> GET /suggest 200 (x4) $BODY"

# 6. structured JSON log events
"${COMPOSE[@]}" logs --no-color --no-log-prefix search-service >"$CONTAINER_LOG" 2>&1
python3 - "$CONTAINER_LOG" <<'PY' || fail "container logs missing JSON events"
import json, sys
want = {"search_executed", "api_document_indexed"}
info = {"sqs_consumer_started", "sqs_consumer_error"}
seen = {}
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    try:
        rec = json.loads(line)
    except ValueError:
        continue
    if isinstance(rec, dict) and rec.get("event") in want | info:
        seen[rec["event"]] = seen.get(rec["event"], 0) + 1
print("json events:", {k: seen.get(k, 0) for k in sorted(want | info)})
sys.exit(0 if want <= seen.keys() else 1)
PY
pass "6 container logs have JSON events search_executed and api_document_indexed"

# 7. teardown + exit status happen in the EXIT trap
