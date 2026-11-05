#!/usr/bin/env bash
# Remove every container, volume, network and locally built image of ONE run (COMPOSE_PROJECT_NAME),
# then verify nothing carrying that run token remains. Selection is by exact label value or exact
# derived name only (never a prefix/substring), so a project named "$P-other" is never touched.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
load_env
P="$COMPOSE_PROJECT_NAME"
APP_IMAGE="$P-slack-mock:local"
by_label() { # kind key -> ids whose label key equals $P exactly
  case $1 in
    container) docker ps -aq --filter "label=$2=$P" ;;
    volume) docker volume ls -q --filter "label=$2=$P" ;;
    network) docker network ls -q --filter "label=$2=$P" ;;
    image) docker image ls -q --filter "label=$2=$P" ;;
  esac
}
owned() { # kind -> ids owned by this run, deduplicated
  { by_label "$1" com.docker.compose.project; by_label "$1" com.devin.collection.run
    [[ $1 != image ]] || docker image ls -q --filter "reference=$APP_IMAGE"; } | sort -u
}
start=$(date +%s.%N)

compose --profile mcp down --volumes --remove-orphans --timeout 10 >&2

# Stragglers (e.g. interrupted `compose run` MCP containers), selected strictly by exact labels.
for kind in container volume network image; do
  ids=$(owned "$kind")
  [[ -z "$ids" ]] || docker "$kind" rm -f $ids >/dev/null
done
if [[ "${RESET_KEEP_ENV:-0}" != "1" ]]; then rm -f "$ENV_FILE" "$ENV_FILE.lock" "$ENV_FILE.tmp"; fi
end=$(date +%s.%N)

left=0
echo "remaining resources for run $P:"
for kind in container volume network image; do
  n=$(owned "$kind" | grep -c . || true)
  printf '  %-10s %s\n' "$kind" "$n"; left=$((left + n))
done
# Exact-token match in files: $P not followed by another name character (so "$P-other" is not a hit).
files=$(grep -rlE --exclude-dir=.venv --exclude-dir=.git "$P([^a-z0-9-]|\$)" "$COLLECTION_DIR" 2>/dev/null || true)
n=$(printf '%s' "$files" | grep -c . || true); printf '  %-10s %s\n' files "$n"; left=$((left + n))
printf 'reset of %s took %.1fs\n' "$P" "$(echo "$end - $start" | bc)"
[[ $left -eq 0 ]] || die "$left resources still carry run token $P"
echo "verified: nothing carrying $P remains"
