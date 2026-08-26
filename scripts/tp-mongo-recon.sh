#!/usr/bin/env bash
# Full reconciliation sequence for the ow_tp_<NS> MongoDB run:
#   1. snapshot every recomputed target value
#   2. rerun both migrations (idempotency evidence)
#   3. three-way report (Atlas vs Oracle vs manifest) with the pre-rerun snapshot
# Exits nonzero if any check fails.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

NS="${NS:?NS is required, e.g. NS=demo1}"
MANIFEST="$REPO_ROOT/testdata/legacy/manifests/$NS.json"
BATCH_NO="${BATCH_NO:-$(python3 -c "import json,sys;m=json.load(open(sys.argv[1]));print(m['seed_legacy_params']['oracle.OW_BILLING.CUSTOMER_MASTER']['batch_no'])" "$MANIFEST")}"
ORACLE_BILLING_DB_PORT="${ORACLE_BILLING_DB_PORT:-52521}"
export ORACLE_BILLING_DB_PORT

RUN() {
    uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 \
        --with requests==2.32.3 python3 "$@"
}

SNAPSHOT="$(mktemp /tmp/tp-recon-snapshot-"$NS".XXXXXX.json)"
trap 'rm -f "$SNAPSHOT"' EXIT

echo "== snapshot (pre-rerun target state) =="
RUN scripts/tp_mongo/recon.py snapshot --ns "$NS" --out "$SNAPSHOT"

echo "== idempotency rerun: invoices =="
RUN scripts/tp_mongo/migrate_invoices.py --ns "$NS" --batch-no "$BATCH_NO" \
    --reruns 0 --report "/tmp/tp-recon-invoices-rerun.$NS.recon.json"

echo "== idempotency rerun: customers =="
RUN scripts/tp_mongo/migrate_customers.py migrate --ns "$NS" --batch-no "$BATCH_NO"

echo "== report =="
RUN scripts/tp_mongo/recon.py report --ns "$NS" --snapshot-before "$SNAPSHOT"
