#!/usr/bin/env bash
# Run the document-service suite (or a slice of it) N times and report how often it fails.
# Usage: scripts/flake_rate.sh [runs] [pytest args...]
set -uo pipefail
cd "$(dirname "$0")/.."
runs="${1:-20}"
shift || true
pytest_cmd="${PYTEST:-pytest}"
fails=0
declare -A failed_tests=()
for i in $(seq 1 "$runs"); do
  out="$($pytest_cmd -q -p no:cacheprovider -p no:randomly "$@" 2>&1)"
  if [ $? -ne 0 ]; then
    fails=$((fails + 1))
    while read -r t; do failed_tests["$t"]=$(( ${failed_tests["$t"]:-0} + 1 )); done \
      < <(printf '%s\n' "$out" | sed -n 's/^FAILED \([^ ]*\).*/\1/p')
    echo "run $i: FAIL $(printf '%s\n' "$out" | tail -1)"
  else
    echo "run $i: pass $(printf '%s\n' "$out" | tail -1)"
  fi
done
echo "---"
echo "failed $fails of $runs runs ($(( fails * 100 / runs ))%)"
for t in "${!failed_tests[@]}"; do echo "  ${failed_tests[$t]}x $t"; done
[ "$fails" -eq 0 ]
