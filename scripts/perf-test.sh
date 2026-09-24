#!/usr/bin/env bash
# scripts/perf-test.sh — simple before/after measurement of POST /api/v1/reports
# Requires: curl, the app running on localhost:8091 with SPRING_PROFILES_ACTIVE=local
set -euo pipefail

BASE_URL="${1:-http://localhost:8091}"
N="${2:-50}"

echo "=== Performance test: $N report requests to $BASE_URL ==="

PAYLOAD='{"reportName":"Perf Test Report","category":"USAGE_ANALYTICS","reportType":"CSV","requestedBy":"perf-tester"}'

total_ms=0
completed=0
failed=0

for i in $(seq 1 "$N"); do
  start_ns=$(date +%s%N)
  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$BASE_URL/api/v1/reports" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
  end_ns=$(date +%s%N)

  elapsed_ms=$(( (end_ns - start_ns) / 1000000 ))
  total_ms=$((total_ms + elapsed_ms))

  if [ "$http_code" = "202" ]; then
    completed=$((completed + 1))
  else
    failed=$((failed + 1))
  fi
done

avg_ms=$((total_ms / N))

echo "Results:"
echo "  Total requests: $N"
echo "  Accepted (202): $completed"
echo "  Failed:         $failed"
echo "  Total time:     ${total_ms}ms"
echo "  Avg latency:    ${avg_ms}ms per request"

# Wait a bit for async generation, then check completed count
sleep 3
completed_reports=$(curl -s "$BASE_URL/api/v1/reports?status=COMPLETED" | grep -o '"total":[0-9]*' | head -1 || echo "total:unknown")
echo "  Completed reports: $completed_reports"
echo "=== Done ==="
