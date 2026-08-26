#!/usr/bin/env bash
# Migrate OW_BILLING.CUSTOMER_MASTER + ENTITY_ATTR_VALUE into ow_tp_<NS>.customers,
# rerun the migration to prove convergence, and reconcile the target against the
# source manifest.
#
#   NS=demo1 BATCH_NO=23746131 scripts/tp-mongo-migrate-customers.sh
#
# Requires MONGODB_ATLAS_URI and a reachable Oracle billing estate (DB_PORT).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${NS:?NS is required, e.g. NS=demo1}"
MANIFEST="${MANIFEST:-$REPO_ROOT/testdata/legacy/manifests/$NS.json}"
BATCH_NO="${BATCH_NO:-$(python3 -c "import json,sys;m=json.load(open(sys.argv[1]));print(m['seed_legacy_params']['oracle.OW_BILLING.CUSTOMER_MASTER']['batch_no'])" "$MANIFEST")}"
RECON_OUT="${RECON_OUT:-$REPO_ROOT/docs/tech-partnerships/recon/customer_master.$NS.recon.json}"
RUN_MODE="${RUN_MODE:-live}"

RUN=(uv run --no-project --with pymongo==4.10.1 --with oracledb==2.5.1
     "$REPO_ROOT/scripts/tp_mongo/migrate_customers.py")
COMMON=(--ns "$NS" --batch-no "$BATCH_NO")

echo "== migration run 1 =="
"${RUN[@]}" migrate "${COMMON[@]}"
FP_BEFORE="$("${RUN[@]}" fingerprint "${COMMON[@]}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["fingerprint"])')"

echo "== migration run 2 (idempotency rerun) =="
"${RUN[@]}" migrate "${COMMON[@]}"
FP_AFTER="$("${RUN[@]}" fingerprint "${COMMON[@]}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["fingerprint"])')"

echo "== reconciliation =="
"${RUN[@]}" recon "${COMMON[@]}" \
  --manifest "$MANIFEST" --out "$RECON_OUT" --run-mode "$RUN_MODE" \
  --fingerprint-before "$FP_BEFORE" --fingerprint-after "$FP_AFTER"
