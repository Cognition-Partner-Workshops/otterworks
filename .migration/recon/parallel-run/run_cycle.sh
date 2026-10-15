#!/usr/bin/env bash
# One coexistence-window cycle on the disposable procs namespace NS (default p5):
#   1. replay procs/scenarios (kind: procedure) against the legacy app   -> cycle-N/cycle.json
#   2. procs parity (make procs-parity, all 24 transcripts) against the migrated stack at
#      BILLING_SVC_URL: billing-service on Atlas billing_migration, /internal/reset fed by the
#      billing_ro baseline fixture (billing_mig)                        -> cycle-N/parity/
#   3. delta sync legacy -> Atlas billing_migration (app/delta.py)       -> cycle-N/delta.json
#      (also undoes the last parity scenario's writes, so the cycle state is what recon sees)
#   4. mongo-recon-harness, mode continuous, all seven collections        -> cycle-N/recon/
# Secrets by name: BILLING_RO_PASSWORD (session-local, never committed) builds POSTGRESQL_RO_DSN
# for the billing_ro role; MONGODB_ATLAS_URI comes from the environment. Run in a one-shot shell:
#   NS=p5 PROCS_DB_PORT=55930 BILLING_RO_PASSWORD=... BILLING_SVC_URL=http://127.0.0.1:12930 \
#     OUT_ROOT=.migration/recon/parallel-run/s5.2 .migration/recon/parallel-run/run_cycle.sh 1
# OUT_ROOT defaults to the s5.1 layout (.migration/recon/parallel-run); set PARITY=skip to run the
# s5.1 shape (recon only).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
CYCLE="${1:?cycle number}"
NS="${NS:-p5}"
# same port convention as the Makefile procs targets: 55432 + crc32(NS) % 1000 (p5 -> 55930)
PROCS_DB_PORT="${PROCS_DB_PORT:-$(NS="$NS" python3 -c 'import os, zlib; print(55432 + zlib.crc32(os.environ["NS"].encode()) % 1000)')}"
PLUGIN="${MONGO_MIGRATION_PLUGIN:-$HOME/repos/mongo-migration-plugin}"
RECON="${RECON_BIN:-$HOME/.venvs/recon/bin/recon}"
OUT="${OUT_ROOT:-.migration/recon/parallel-run}/cycle-${CYCLE}"
PARITY="${PARITY:-run}"
: "${BILLING_RO_PASSWORD:?set BILLING_RO_PASSWORD (never commit the value)}"
: "${MONGODB_ATLAS_URI:?MONGODB_ATLAS_URI is not set}"
export POSTGRESQL_RO_DSN
POSTGRESQL_RO_DSN="$(NS="$NS" PROCS_DB_PORT="$PROCS_DB_PORT" python3 -c 'import json, os
print(json.dumps({"user": "billing_ro", "password": os.environ["BILLING_RO_PASSWORD"], "host": "127.0.0.1",
  "port": int(os.environ["PROCS_DB_PORT"]), "database": "billing_" + os.environ["NS"], "schema": "billing"}))')"
if [ "$PARITY" != "skip" ]; then
  : "${BILLING_SVC_URL:?set BILLING_SVC_URL (billing-service on Atlas billing_migration) or PARITY=skip}"
  # the parity target must be the cluster + database delta and recon write to; /health reports the
  # database name and a fingerprint (sha256 of the URI host) so a green run on another stack cannot count
  curl -fsS "$BILLING_SVC_URL/health" | python3 -c 'import hashlib, json, os, sys, urllib.parse
h = json.load(sys.stdin)
want = {"database": "billing_migration",
        "cluster": hashlib.sha256(urllib.parse.urlsplit(os.environ["MONGODB_ATLAS_URI"]).hostname.encode()).hexdigest()[:12]}
got = {k: h.get(k) for k in want}
assert got == want, f"BILLING_SVC_URL is not on the delta/recon target: {got} != {want}"'
fi
mkdir -p "$OUT"
NS="$NS" python3 .migration/recon/parallel-run/cycle.py --cycle "$CYCLE" --out "$OUT/cycle.json"
PARITY_RC=0
if [ "$PARITY" != "skip" ]; then
  rm -rf procs/reports
  # the harness resets Atlas before every transcript, so the delta below must run even when parity is red
  set +e
  BILLING_SVC_URL="$BILLING_SVC_URL" make -s procs-parity NS="$NS" | tee "$OUT/parity.log"
  PARITY_RC=${PIPESTATUS[0]}
  set -e
  # procs/reports/ is gitignored: keep the report as committed cycle evidence, tagged with the target
  python3 - "$OUT/parity" "$BILLING_SVC_URL" "$PARITY_RC" <<'PY'
import json, pathlib, shutil, sys
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
src = pathlib.Path("procs/reports")
if (src / "parity.md").exists():
    shutil.copy(src / "parity.md", out / "parity.md")
if (src / "parity.json").exists():
    report = json.load(open(src / "parity.json"))
    counts = {k: sum(r["status"] == k for r in report["results"]) for k in ("PASS", "FAIL", "SKIP")}
    report["target"] = {"billing_svc_url": sys.argv[2], "target_class": "migration_cluster", "database": "billing_migration"}
    report["counts"] = counts
    (out / "parity.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    assert sys.argv[3] != "0" or counts == {"PASS": 24, "FAIL": 0, "SKIP": 0}, counts
PY
fi
DELTA_LOG="$(realpath -m "$OUT")/delta.json"
(cd services/billing-service && uv run python -m app.delta --source-dsn-secret POSTGRESQL_RO_DSN \
  --target-uri-secret MONGODB_ATLAS_URI --log "$DELTA_LOG")
if [ "$PARITY_RC" -ne 0 ]; then
  echo "parity FAILED (rc=$PARITY_RC): Atlas re-synced to the legacy cycle state, recon skipped; record the red run in drift.md" >&2
  exit "$PARITY_RC"
fi
"$RECON" run --unit "parallel-run-cycle-${CYCLE}" --family postgresql --mapping .migration/mapping_spec.json \
  --tolerances .migration/recon_tolerances.json \
  --canonicalization "$PLUGIN/skills/mongo-migration/profiles/postgresql.md" \
  --mode continuous --target-class migration_cluster \
  --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI --target-db billing_migration \
  --allowed-targets-file .migration/allowed_targets.json --source-concurrency 1 --seed 1 \
  --out "$OUT/recon/"
python3 -c 'import json, sys; r = json.load(open(sys.argv[1])); print("recon verdict:", r.get("verdict") or r.get("status") or r)' "$OUT/recon/result.json"
