#!/usr/bin/env bash
# Replay the transcript recorded against the monolith on main through the strangler edge of
# docker-compose.portal.yml, then show which upstream answered each module.
#
#   services/preferences-service/parity/run.sh            # fresh stack (down -v, up --build)
#   BUILD=0 services/preferences-service/parity/run.sh    # use already-built images
#
# Exit code is non-zero if any of the 95 cases differ from the transcript or a route check fails.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
PORT="${PORTAL_EDGE_PORT:-8095}"
BASE="${BASE:-http://localhost:${PORT}}"
OUT="${OUT:-$ROOT/.demo/preferences-service/$(date -u +%Y%m%dT%H%M%SZ)}"
COMPOSE=(docker compose -p "${PROJECT:-portal-strangler}" -f "$ROOT/docker-compose.portal.yml")

(cd "$HERE/transcripts" && sha256sum -c --quiet SHA256SUMS)

# The corpus is ordered and stateful: both databases must start empty.
"${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
if [[ "${BUILD:-1}" == "1" ]]; then
  "${COMPOSE[@]}" up -d --build --wait
else
  "${COMPOSE[@]}" up -d --no-build --wait
fi

mkdir -p "$OUT"
rc=0
python3 "$ROOT/services/legacy-portal/parity/replay.py" --base "$BASE" \
  --java-capture "$HERE/transcripts/monolith-main.json" \
  --context all --stage full --strict-media-type --out "$OUT" || rc=$?

served_by() { curl -s -o /dev/null -D - "$BASE$1" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-served-by"{print $2}'; }
check() {
  local path="$1" want="$2" got
  got="$(served_by "$path")"
  if [[ "$got" == "$want" ]]; then res=identical; else res=failed; rc=1; fi
  printf '| `GET %s` | %s | %s | %s |\n' "$path" "$want" "${got:-none}" "$res"
}
{
  echo "| route | expected upstream | X-Served-By | result |"
  echo "|---|---|---|---|"
  check /health legacy-portal
  check /api/announcements legacy-portal
  check /api/feedback/average-rating legacy-portal
  check /api/preferences/alice preferences-service
  check /api/preferences preferences-service
  check /API/preferences/alice legacy-portal
  check /api/preferencesX legacy-portal
  mono="$("${COMPOSE[@]}" exec -T legacy-portal curl -s -o /dev/null -w '%{http_code}' http://localhost:8095/api/preferences/alice)"
  [[ "$mono" == "404" ]] && res=identical || { res=failed; rc=1; }
  printf '| `GET /api/preferences/alice` direct to legacy-portal | 404 | %s | %s |\n' "$mono" "$res"
} | tee "$OUT/ROUTES.md"

echo "evidence: $OUT"
exit "$rc"
