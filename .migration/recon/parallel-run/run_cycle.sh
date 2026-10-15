#!/usr/bin/env bash
# One coexistence-window cycle on the disposable procs namespace NS (default p5):
#   1. replay procs/scenarios (kind: procedure) against the legacy app   -> cycle-N/cycle.json
#   2. delta sync legacy -> Atlas billing_migration (app/delta.py)       -> cycle-N/delta.json
#   3. mongo-recon-harness, mode continuous, all seven collections        -> cycle-N/recon/
# Secrets by name: BILLING_RO_PASSWORD (session-local, never committed) builds POSTGRESQL_RO_DSN
# for the billing_ro role; MONGODB_ATLAS_URI comes from the environment. Run in a one-shot shell:
#   NS=p5 PROCS_DB_PORT=55930 BILLING_RO_PASSWORD=... .migration/recon/parallel-run/run_cycle.sh 1
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
CYCLE="${1:?cycle number}"
NS="${NS:-p5}"
PROCS_DB_PORT="${PROCS_DB_PORT:-55930}"
PLUGIN="${MONGO_MIGRATION_PLUGIN:-$HOME/repos/mongo-migration-plugin}"
RECON="${RECON_BIN:-$HOME/.venvs/recon/bin/recon}"
OUT=".migration/recon/parallel-run/cycle-${CYCLE}"
: "${BILLING_RO_PASSWORD:?set BILLING_RO_PASSWORD (never commit the value)}"
: "${MONGODB_ATLAS_URI:?MONGODB_ATLAS_URI is not set}"
export POSTGRESQL_RO_DSN
POSTGRESQL_RO_DSN="$(NS="$NS" PROCS_DB_PORT="$PROCS_DB_PORT" python3 -c 'import json, os
print(json.dumps({"user": "billing_ro", "password": os.environ["BILLING_RO_PASSWORD"], "host": "127.0.0.1",
  "port": int(os.environ["PROCS_DB_PORT"]), "database": "billing_" + os.environ["NS"], "schema": "billing"}))')"
mkdir -p "$OUT"
NS="$NS" python3 .migration/recon/parallel-run/cycle.py --cycle "$CYCLE" --out "$OUT/cycle.json"
(cd services/billing-service && uv run python -m app.delta --source-dsn-secret POSTGRESQL_RO_DSN \
  --target-uri-secret MONGODB_ATLAS_URI --log "../../$OUT/delta.json")
"$RECON" run --unit "parallel-run-cycle-${CYCLE}" --family postgresql --mapping .migration/mapping_spec.json \
  --tolerances .migration/recon_tolerances.json \
  --canonicalization "$PLUGIN/skills/mongo-migration/profiles/postgresql.md" \
  --mode continuous --target-class migration_cluster \
  --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI --target-db billing_migration \
  --allowed-targets-file .migration/allowed_targets.json --source-concurrency 1 --seed 1 \
  --out "$OUT/recon/"
python3 -c 'import json, sys; r = json.load(open(sys.argv[1])); print("recon verdict:", r.get("verdict") or r.get("status") or r)' "$OUT/recon/result.json"
