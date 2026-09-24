#!/usr/bin/env bash
# Measures end-to-end report latency: POST /api/v1/reports then poll GET /api/v1/reports/{id}
# until status is COMPLETED or FAILED. Prints p50 / p95 / max and a failure count.
#
# Usage:
#   scripts/perf-report-latency.sh [requests=50] [concurrency=5] [category=USAGE_ANALYTICS] [type=CSV]
# Env:
#   BASE_URL      default http://localhost:8091
#   POLL_INTERVAL seconds between status polls, default 0.05
#   POLL_TIMEOUT  seconds before a request is counted as failed, default 60
#
# Methodology: wall-clock time per request from just before the POST is sent until the first poll
# that observes a terminal status, measured with `date +%s%N` (ms resolution). `concurrency`
# requests are in flight at once (xargs -P). Percentiles are nearest-rank over all samples.
set -euo pipefail

REQUESTS=${1:-50}
CONCURRENCY=${2:-5}
CATEGORY=${3:-USAGE_ANALYTICS}
TYPE=${4:-CSV}
BASE_URL=${BASE_URL:-http://localhost:8091}
POLL_INTERVAL=${POLL_INTERVAL:-0.05}
POLL_TIMEOUT=${POLL_TIMEOUT:-60}

for tool in curl jq xargs; do
  command -v "$tool" >/dev/null || { echo "missing: $tool" >&2; exit 1; }
done

export BASE_URL POLL_INTERVAL POLL_TIMEOUT CATEGORY TYPE

one_request() {
  local i=$1
  local body
  body=$(jq -nc --arg n "perf-$i" --arg c "$CATEGORY" --arg t "$TYPE" \
    '{reportName:$n, category:$c, reportType:$t, requestedBy:"perf-script",
      dateFrom:"2024-01-01T00:00:00Z", dateTo:"2024-01-31T00:00:00Z", parameters:{run:$n}}')
  local start end id status
  start=$(date +%s%N)
  id=$(curl -sS -X POST "$BASE_URL/api/v1/reports" -H 'Content-Type: application/json' -d "$body" | jq -r '.id')
  if [[ -z "$id" || "$id" == "null" ]]; then echo "FAILED 0 post"; return; fi
  local deadline=$(( $(date +%s) + POLL_TIMEOUT ))
  while :; do
    status=$(curl -sS "$BASE_URL/api/v1/reports/$id" | jq -r '.status')
    case "$status" in
      COMPLETED|FAILED) break ;;
    esac
    if (( $(date +%s) > deadline )); then status=TIMEOUT; break; fi
    sleep "$POLL_INTERVAL"
  done
  end=$(date +%s%N)
  echo "$status $(( (end - start) / 1000000 )) $id"
}
export -f one_request

results=$(seq 1 "$REQUESTS" | xargs -P "$CONCURRENCY" -I{} bash -c 'one_request {}')

total=$(echo "$results" | wc -l | tr -d ' ')
ok=$(echo "$results" | grep -c '^COMPLETED' || true)
sorted=$(echo "$results" | grep '^COMPLETED' | awk '{print $2}' | sort -n)
pct() { echo "$sorted" | awk -v p="$1" '{a[NR]=$1} END { if (NR==0) {print "n/a"; exit}; i=int((p/100)*NR+0.999999); if(i<1)i=1; print a[i] }'; }

echo "requests=$total completed=$ok failed=$((total - ok)) concurrency=$CONCURRENCY category=$CATEGORY type=$TYPE"
echo "latency_ms p50=$(pct 50) p95=$(pct 95) max=$(echo "$sorted" | tail -1) min=$(echo "$sorted" | head -1)"
