#!/usr/bin/env bash
# s6.2 catch-up recon at the declared freeze watermark (plan step s6.2-catch-up-recon).
#   0. watermark --check : the legacy source still matches .migration/recon/freeze/watermark.json
#   1. procs parity (all 24 transcripts) against billing-service on Atlas billing_migration -> parity/
#      (the harness resets Atlas before every transcript, so Atlas is churned here on purpose)
#   2. final delta: s5.1 keyed diff (app/delta.py, no watermark column exists) legacy -> Atlas -> delta.json
#   3. the full recon gate, mode live, target_class migration_cluster, at exactly that state -> recon/
#   4. delta again: must be a no-op (0 upserts, 0 deletes) -> delta-rerun.json
#   5. watermark --check again: the source did not move while 1-4 ran, so the recon is AT the watermark
# Never replays anything against the legacy source (unlike run_cycle.sh); the legacy side is SELECT only.
# Needs: POSTGRESQL_RO_DSN (from the secret OW_BILLING_PG_RO_DSN), MONGODB_ATLAS_URI, RECON_REDACT_SALT,
# BILLING_SVC_URL (billing-service already running on Atlas billing_migration), the plugin and recon venv.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
PLUGIN="${MONGO_MIGRATION_PLUGIN:-$HOME/repos/mongo-migration-plugin}"
RECON="${RECON_BIN:-$HOME/.venvs/recon/bin/recon}"
PY="${RECON_PY:-$HOME/.venvs/recon/bin/python}"
OUT=.migration/recon/freeze
WM="$OUT/watermark.json"
: "${POSTGRESQL_RO_DSN:?export the value of the secret OW_BILLING_PG_RO_DSN as POSTGRESQL_RO_DSN}"
: "${MONGODB_ATLAS_URI:?MONGODB_ATLAS_URI is not set}"
: "${RECON_REDACT_SALT:?RECON_REDACT_SALT is not set (artifacts must be salted)}"
: "${BILLING_SVC_URL:?set BILLING_SVC_URL (billing-service on Atlas billing_migration)}"
test -s "$WM" || { echo "declare the watermark first: $PY $OUT/watermark.py --out $WM" >&2; exit 2; }
curl -fsS "$BILLING_SVC_URL/health" | python3 -c 'import hashlib, json, os, sys, urllib.parse
h = json.load(sys.stdin)
want = {"database": "billing_migration",
        "cluster": hashlib.sha256(urllib.parse.urlsplit(os.environ["MONGODB_ATLAS_URI"]).hostname.encode()).hexdigest()[:12]}
got = {k: h.get(k) for k in want}
assert got == want, f"BILLING_SVC_URL is not on the delta/recon target: {got} != {want}"'
"$PY" "$OUT/watermark.py" --check "$WM" > "$OUT/watermark-check-before.json"
rm -rf procs/reports
BILLING_SVC_URL="$BILLING_SVC_URL" make -s procs-parity NS=mig | tee "$OUT/parity.log"
python3 - "$OUT/parity" "$BILLING_SVC_URL" <<'PY'
import json, pathlib, shutil, sys
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
src = pathlib.Path("procs/reports")
shutil.copy(src / "parity.md", out / "parity.md")
report = json.load(open(src / "parity.json"))
counts = {k: sum(r["status"] == k for r in report["results"]) for k in ("PASS", "FAIL", "SKIP")}
report["target"] = {"billing_svc_url": sys.argv[2], "target_class": "migration_cluster", "database": "billing_migration"}
report["counts"] = counts
(out / "parity.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
assert counts == {"PASS": 24, "FAIL": 0, "SKIP": 0}, counts
PY
ABS="$(realpath -m "$OUT")"
(cd services/billing-service && uv run python -m app.delta --source-dsn-secret POSTGRESQL_RO_DSN \
  --target-uri-secret MONGODB_ATLAS_URI --log "$ABS/delta.json")
rm -rf "$OUT/recon"
"$RECON" run --unit freeze-watermark --family postgresql --mapping .migration/mapping_spec.json \
  --tolerances .migration/recon_tolerances.json \
  --canonicalization "$PLUGIN/skills/mongo-migration/profiles/postgresql.md" \
  --mode live --target-class migration_cluster \
  --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI --target-db billing_migration \
  --allowed-targets-file .migration/allowed_targets.json --source-concurrency 1 --seed 1 \
  --out "$OUT/recon/"
(cd services/billing-service && uv run python -m app.delta --source-dsn-secret POSTGRESQL_RO_DSN \
  --target-uri-secret MONGODB_ATLAS_URI --log "$ABS/delta-rerun.json")
python3 - "$OUT" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
rerun = json.load(open(out / "delta-rerun.json"))
moved = {c: v for c, v in rerun["collections"].items() if v.get("upserted") or v.get("deleted")}
assert not moved, f"delta re-run was not a no-op: {moved}"
r = json.load(open(out / "recon/result.json"))
print("recon verdict:", r.get("verdict") or r.get("status"), "| merge_eligible:", r.get("merge_eligible"))
PY
"$PY" "$OUT/watermark.py" --check "$WM" > "$OUT/watermark-check-after.json"
echo "freeze held: $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["freeze_held"])' "$OUT/watermark-check-after.json")"
