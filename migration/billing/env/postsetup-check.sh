#!/usr/bin/env bash
# Post-setup checks for OtterWorks billing migration workers (Oracle OW_BILLING -> MongoDB Atlas).
#
# Connectivity policy (decision d-connectivity-policy, do not reopen): auto = live when the
# named secret is present and reachable, local fallback otherwise.
#   OW_BILLING_ENV_MODE=online  live only; a missing/unreachable live endpoint is a failure
#   OW_BILLING_ENV_MODE=auto    live first, then the local fallback (default)
#
# Live endpoints are referenced by secret NAME only and are never printed:
#   MONGODB_ATLAS_URI      Atlas connection string
#   OW_TP_ORACLE_RO_DSN    read-only Oracle login; JSON {user,password,dsn} or a plain connect string
# Local fallbacks: a `mongo:7` container (ow-billing-mongo, 127.0.0.1:27117) and the repo's
# Oracle Free fixture (`make oracle-billing-up`, localhost:52521/FREEPDB1).
#
# Checks: mongosh ping; python-oracledb (thin) `SELECT 1 FROM dual`; `make tp-validate-schemas`.
# A result marked "fallback" came from a local fixture and is never merge evidence.
#
# Usage: migration/billing/env/postsetup-check.sh [setup|check|all]   (default: all)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MODE="${OW_BILLING_ENV_MODE:-auto}"
VENV="${OW_BILLING_VENV:-$HOME/.venvs/ow-billing}"
PY="$VENV/bin/python"
LOCAL_MONGO_NAME="ow-billing-mongo"
LOCAL_MONGO_PORT="${OW_BILLING_LOCAL_MONGO_PORT:-27117}"
ORACLE_FIXTURE_PORT="${ORACLE_BILLING_DB_PORT:-52521}"
REPORT_DIR="$REPO_ROOT/migration/billing/env/reports"
REPORT="$REPORT_DIR/postsetup-check-$(date -u +%Y%m%dT%H%M%SZ).log"
ACTION="${1:-all}"

case "$MODE" in online|auto) ;; *) echo "OW_BILLING_ENV_MODE must be online or auto (got: $MODE)" >&2; exit 2 ;; esac

mkdir -p "$REPORT_DIR"
exec > >(tee -a "$REPORT") 2>&1
redact() { sed -E 's#mongodb(\+srv)?://[^[:space:]"]+#mongodb://<redacted>#g'; }
log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }
FAILED=0
RESULTS=()
record() { RESULTS+=("$1 $2 $3"); [ "$2" = FAIL ] && FAILED=1; return 0; }

setup() {
  log "setup: mode=$MODE venv=$VENV"
  for t in mongosh mongodump mongoimport mongorestore atlas uv docker make; do
    command -v "$t" >/dev/null 2>&1 || { log "setup: missing tool: $t"; FAILED=1; }
  done
  mkdir -p "$(dirname "$VENV")"
  [ -x "$PY" ] || uv venv --python /usr/bin/python3 "$VENV"
  uv pip install --python "$PY" "oracledb==2.5.1" "pymongo==4.10.1" >/dev/null
  "$PY" -c 'import oracledb, pymongo; print(f"setup: python-oracledb {oracledb.__version__} (thin), pymongo {pymongo.__version__}")'
  docker image inspect mongo:7 >/dev/null 2>&1 || docker pull mongo:7
  log "setup: mongo:7 image present; Oracle fixture via 'make oracle-billing-up' (not started here)"
}

check_mongo() {
  if [ -n "${MONGODB_ATLAS_URI:-}" ]; then
    if out=$(timeout 60 mongosh "$MONGODB_ATLAS_URI" --quiet --eval 'const r=db.adminCommand({ping:1}); print("ok="+r.ok+" host="+db.hello().me)' 2>&1 | redact); then
      log "mongo: live ping $out"; record mongo PASS live; return
    fi
    log "mongo: live ping failed: $out"
  else
    log "mongo: MONGODB_ATLAS_URI not set"
  fi
  if [ "$MODE" = online ]; then record mongo FAIL live; return; fi
  if ! docker ps --format '{{.Names}}' | grep -qx "$LOCAL_MONGO_NAME"; then
    docker rm -f "$LOCAL_MONGO_NAME" >/dev/null 2>&1 || true
    docker run -d --name "$LOCAL_MONGO_NAME" -p "127.0.0.1:${LOCAL_MONGO_PORT}:27017" mongo:7 >/dev/null
  fi
  for _ in $(seq 1 30); do
    if out=$(mongosh "mongodb://127.0.0.1:${LOCAL_MONGO_PORT}/" --quiet --eval 'print("ok="+db.adminCommand({ping:1}).ok+" host="+db.serverStatus().host)' 2>&1); then
      log "mongo: FALLBACK mongo:7 ping $out"; record mongo PASS fallback; return
    fi
    sleep 1
  done
  log "mongo: fallback mongo:7 ping failed: $out"; record mongo FAIL fallback
}

oracle_select1() {  # $1 = live|fixture
  timeout 90 "$PY" - "$1" <<'PY'
import json, os, sys, oracledb
source = sys.argv[1]
if source == "live":
    raw = os.environ["OW_TP_ORACLE_RO_DSN"]
    try:
        cfg = json.loads(raw)
        kw = dict(user=cfg["user"], password=cfg["password"], dsn=cfg["dsn"])
    except (ValueError, KeyError, TypeError):
        kw = dict(dsn=raw)
else:
    kw = dict(user="ow_billing", password="ow_billing",
              dsn=f"localhost:{os.environ['ORACLE_FIXTURE_PORT']}/FREEPDB1")
with oracledb.connect(**kw) as con:
    cur = con.cursor()
    cur.execute("SELECT 1 FROM dual"); one = cur.fetchone()[0]
    cur.execute("SELECT USER FROM dual"); who = cur.fetchone()[0]
    print(f"thin={oracledb.is_thin_mode()} select1={one} principal={who} server={con.version}")
PY
}

check_oracle() {
  if [ -n "${OW_TP_ORACLE_RO_DSN:-}" ]; then
    if out=$(oracle_select1 live 2>&1); then
      log "oracle: live $out"; record oracle PASS live; return
    fi
    log "oracle: live SELECT 1 failed: $(printf '%s' "$out" | tail -1)"
  else
    log "oracle: OW_TP_ORACLE_RO_DSN not set"
  fi
  if [ "$MODE" = online ]; then record oracle FAIL live; return; fi
  if ! docker ps --filter name=otterworks-oracle-billing --filter health=healthy --format '{{.Names}}' | grep -q .; then
    log "oracle: fixture not running/healthy; start it with 'make oracle-billing-up' (10-20 min on first boot)"
    record oracle FAIL fallback-unavailable; return
  fi
  if out=$(ORACLE_FIXTURE_PORT="$ORACLE_FIXTURE_PORT" oracle_select1 fixture 2>&1); then
    log "oracle: FALLBACK fixture $out (schema owner, not a read-only principal)"; record oracle PASS fallback; return
  fi
  log "oracle: fallback fixture SELECT 1 failed: $(printf '%s' "$out" | tail -1)"; record oracle FAIL fallback
}

check_schemas() {
  if out=$(cd "$REPO_ROOT" && make -s tp-validate-schemas 2>&1); then
    log "schemas: make tp-validate-schemas: $(printf '%s' "$out" | tail -1)"; record schemas PASS local
  else
    log "schemas: make tp-validate-schemas failed:"; printf '%s\n' "$out" | tail -5; record schemas FAIL local
  fi
}

case "$ACTION" in
  setup) setup ;;
  check) check_mongo; check_oracle; check_schemas ;;
  all)   setup; check_mongo; check_oracle; check_schemas ;;
  *) echo "usage: $0 [setup|check|all]" >&2; exit 2 ;;
esac

if [ "${#RESULTS[@]}" -gt 0 ]; then
  log "summary (mode=$MODE):"; printf '  %s\n' "${RESULTS[@]}"
fi
log "report: ${REPORT#$REPO_ROOT/}"
exit $FAILED
