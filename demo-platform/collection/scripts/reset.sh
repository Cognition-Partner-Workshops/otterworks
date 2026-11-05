#!/usr/bin/env bash
# Remove every container, volume, network and locally built image of ONE run (COMPOSE_PROJECT_NAME),
# then verify nothing carrying that run token remains. Never touches other projects.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
load_env
P="$COMPOSE_PROJECT_NAME"
start=$(date +%s.%N)

compose --profile mcp down --volumes --remove-orphans --rmi local --timeout 10 >&2

# Stragglers (e.g. interrupted `compose run` MCP containers) selected strictly by this project's labels.
for kind in container volume network; do
  case $kind in
    container) ids=$(docker ps -aq --filter "label=com.docker.compose.project=$P") ;;
    volume) ids=$(docker volume ls -q --filter "label=com.docker.compose.project=$P") ;;
    network) ids=$(docker network ls -q --filter "label=com.docker.compose.project=$P") ;;
  esac
  [[ -z "$ids" ]] || docker "$kind" rm -f $ids >/dev/null
done
imgs=$(docker image ls -q --filter "label=com.docker.compose.project=$P"; docker image ls -q "$P-*")
[[ -z "$imgs" ]] || docker image rm -f $imgs >/dev/null
if [[ "${RESET_KEEP_ENV:-0}" != "1" ]]; then rm -f "$ENV_FILE" "$ENV_FILE.lock" "$ENV_FILE.tmp"; fi
end=$(date +%s.%N)

left=0
check() { local n; n=$(eval "$2" | wc -l); printf '  %-10s %s\n' "$1" "$n"; left=$((left + n)); }
echo "remaining resources for run $P:"
check containers "docker ps -aq --filter label=com.docker.compose.project=$P; docker ps -aq --filter name=$P"
check volumes    "docker volume ls -q --filter label=com.docker.compose.project=$P; docker volume ls -q --filter name=$P"
check networks   "docker network ls -q --filter label=com.docker.compose.project=$P; docker network ls -q --filter name=$P"
check images     "docker image ls -q --filter label=com.docker.compose.project=$P; docker image ls -q '$P-*'"
check labelled   "docker ps -aq --filter label=com.devin.collection.run=$P; docker volume ls -q --filter label=com.devin.collection.run=$P"
files=$(grep -rlF --exclude-dir=.venv --exclude-dir=.git "$P" "$COLLECTION_DIR" 2>/dev/null || true)
n=$(printf '%s' "$files" | grep -c . || true); printf '  %-10s %s\n' files "$n"; left=$((left + n))
printf 'reset of %s took %.1fs\n' "$P" "$(echo "$end - $start" | bc)"
[[ $left -eq 0 ]] || die "$left resources still carry run token $P"
echo "verified: nothing carrying $P remains"
