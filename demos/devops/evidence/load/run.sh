#!/usr/bin/env bash
# Bounded before/after load per workload on the local kind 1.34 fleet (dev only, read-only on the cluster).
set -uo pipefail
DEMO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
ROOT=$(git -C "$DEMO" rev-parse --show-toplevel)
FLEET="$ROOT/platform/standards/fleet"
OUT="$DEMO/evidence/load"
CONTEXT=kind-devops-20261128-1-34
NAMESPACE=devops-fleet
PROFILE="$DEMO/fixtures/load-profile.json"
SETTLE=${SETTLE:-30}
port=18080
for workload in ${WORKLOADS:-api-gateway auth-service collab-service document-service file-service search-service}; do
  port=$((port + 1))
  kubectl --context "$CONTEXT" -n "$NAMESPACE" port-forward "deployment/$workload" "$port:8080" --address 127.0.0.1 >/dev/null 2>&1 &
  pf=$!
  sleep 3
  for phase in before after; do
    python3 "$FLEET/load_compare.py" capture --profile "$PROFILE" --context "$CONTEXT" --namespace "$NAMESPACE" \
      --deployment "$workload" --url "http://127.0.0.1:$port/work" \
      --json "$OUT/$workload.$phase.json" --markdown "$OUT/$workload.$phase.md"
    echo "$workload $phase capture exit $?"
    [[ $phase == before ]] && sleep "$SETTLE"
  done
  kill "$pf" 2>/dev/null; wait "$pf" 2>/dev/null
  python3 "$FLEET/load_compare.py" compare "$OUT/$workload.before.json" "$OUT/$workload.after.json" \
    --json "$OUT/$workload.comparison.json" --markdown "$OUT/$workload.comparison.md"
  echo "$workload compare exit $?"
  sleep "$SETTLE"
done
