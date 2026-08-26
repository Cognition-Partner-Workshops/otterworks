#!/usr/bin/env bash
# Parent-owned live rollup for the MongoDB migration run.
#
# Runs every unit's migration against the Atlas cluster twice (the second run is
# what proves idempotency) and recomputes each unit's reconciliation from the
# cluster itself. Fixture reconciliations produced while a unit was being built
# are not evidence for this estate; only this uncontended run is.
#
# Usage: scripts/tp-mongo-live-rollup.sh [NS]
set -uo pipefail

NS="${1:-demo}"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${MONGODB_ATLAS_URI:?MONGODB_ATLAS_URI must be set}"
export TP_MONGODB_URI="$MONGODB_ATLAS_URI"
export MONGO_FILES_TARGET=live
export EVIDENCE_DIR="$ROOT/docs/tech-partnerships/recon/evidence"
RUN_DIR="$ROOT/.tp-live/$NS"
mkdir -p "$RUN_DIR" "$EVIDENCE_DIR"

FAILED=()
step() {
  local name="$1"; shift
  echo "=================== $name"
  if "$@" >"$RUN_DIR/$name.log" 2>&1; then
    echo "[ok]     $name"
  else
    echo "[FAILED] $name (see $RUN_DIR/$name.log)"
    FAILED+=("$name")
  fi
  tail -n 25 "$RUN_DIR/$name.log"
}

# --- customers -------------------------------------------------------------
step customers-migrate-1 make mongo-customers-migrate NS="$NS" SUMMARY_OUT="$RUN_DIR/customers.run1.json"
step customers-migrate-2 make mongo-customers-migrate NS="$NS" SUMMARY_OUT="$RUN_DIR/customers.run2.json"
step customers-recon make mongo-customers-recon NS="$NS" RUN_MODE=live \
  RUN_SUMMARIES="$RUN_DIR/customers.run1.json $RUN_DIR/customers.run2.json"

# --- invoices --------------------------------------------------------------
step invoices-migrate-1 migrations/mongodb/mongo_invoices/run.sh migrate --ns "$NS" \
  --summary-out "$RUN_DIR/invoices.run1.json"
step invoices-migrate-2 migrations/mongodb/mongo_invoices/run.sh migrate --ns "$NS" \
  --summary-out "$RUN_DIR/invoices.run2.json"
step invoices-recon migrations/mongodb/mongo_invoices/run.sh recon --ns "$NS" \
  --out "$ROOT/docs/tech-partnerships/recon/mongo_invoices.recon.json" \
  --rerun-summary-a "$RUN_DIR/invoices.run1.json" \
  --rerun-summary-b "$RUN_DIR/invoices.run2.json"

# --- documents (its runner already does migrate x2 + fingerprints + recon) --
step documents-all migrations/mongodb/run_documents_migration.sh "$NS" live

# --- files -----------------------------------------------------------------
step files-migrate-1 uv run migrations/mongodb/mongo_files/migrate.py --ns "$NS"
step files-migrate-2 uv run migrations/mongodb/mongo_files/migrate.py --ns "$NS"
step files-recon uv run migrations/mongodb/mongo_files/recon.py --ns "$NS" \
  --out "$ROOT/docs/tech-partnerships/recon/mongo_files.recon.json"

echo "=================== rollup summary"
for report in "$ROOT"/docs/tech-partnerships/recon/mongo_*.recon.json; do
  python3 - "$report" <<'PY'
import json, sys
path = sys.argv[1]
with open(path) as fh:
    r = json.load(fh)
det = r.get("planted_anomaly_detections", {})
print(json.dumps({
    "unit": r.get("unit"),
    "run_mode": r.get("run_mode"),
    "result": r.get("result"),
    "failed_checks": r.get("failed_checks") or [],
    "anomalies_missing": det.get("missing"),
    "anomalies_unexpected": det.get("unexpected"),
}, sort_keys=True))
PY
done

if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "FAILED STEPS: ${FAILED[*]}"
  exit 1
fi
echo "all steps ok"
