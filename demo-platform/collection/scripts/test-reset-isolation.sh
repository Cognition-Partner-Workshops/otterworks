#!/usr/bin/env bash
# Regression check: resetting run P must not touch a run whose name extends P ("$P-other").
# Starts slack-mock for both runs (separate ports), resets P, asserts P-other's container, volume,
# network and image survive, then resets P-other. Uses throwaway env files only.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
base="collection-isotest$(python3 -c 'import secrets;print(secrets.token_hex(3))')"
other="$base-other"
mkenv() { # file project app-port
  COLLECTION_ENV_FILE="$1" COMPOSE_PROJECT_NAME="$2" "$COLLECTION_DIR/scripts/new-env.sh" 2>/dev/null
  sed -i "s/^COLLECTION_APP_PORT=.*/COLLECTION_APP_PORT=$3/" "$1"
}
up() { COLLECTION_ENV_FILE="$1" bash -c '. "$0"; load_env; compose up -d --build --wait slack-mock' "$COLLECTION_DIR/scripts/lib.sh" >/dev/null 2>&1; }
snapshot() { # project -> resource listing for that exact project
  printf 'containers=%s volumes=%s networks=%s images=%s\n' \
    "$(docker ps -aq --filter "label=com.docker.compose.project=$1" | wc -l)" \
    "$(docker volume ls -q --filter "label=com.docker.compose.project=$1" | wc -l)" \
    "$(docker network ls -q --filter "label=com.docker.compose.project=$1" | wc -l)" \
    "$(docker image ls -q --filter "reference=$1-slack-mock:local" | wc -l)"
}
mkenv "$work/p.env" "$base" 58880
mkenv "$work/o.env" "$other" 58881
up "$work/p.env"; up "$work/o.env"
before=$(snapshot "$other")
echo "before reset of $base: $other $before ; $base $(snapshot "$base")"
COLLECTION_ENV_FILE="$work/p.env" "$COLLECTION_DIR/scripts/reset.sh" 2>/dev/null | tail -2
after=$(snapshot "$other")
echo "after  reset of $base: $other $after ; $base $(snapshot "$base")"
status=0
[[ "$before" == "$after" && "$after" != *"=0"* ]] || { echo "FAIL: $other was modified" >&2; status=1; }
curl -fsS "127.0.0.1:58881/healthz" >/dev/null || { echo "FAIL: $other app not healthy" >&2; status=1; }
COLLECTION_ENV_FILE="$work/o.env" "$COLLECTION_DIR/scripts/reset.sh" 2>/dev/null | tail -1
[[ $status -eq 0 ]] && echo "PASS: overlapping project $other survived reset of $base"
exit $status
