#!/usr/bin/env bash
# One complete recon cycle: every unit's recon gate verbatim, serial (source-load cap 1), plus
# ns-scoped count guard + quarantine ceiling. Usage: cycle.sh <N> [reset]
# With "reset": re-load the Tier-4 replay clones (U6/U7/U8/U9) from head BEFORE gating, as the
# wave3 report describes (Tier-4 replays mutate the clones; U8 does not self-reset).
set -uo pipefail
N=$1; RESET=${2:-}
source "$HOME/cutover_work/pr/env.sh"
REPO="$HOME/cutover_work/otterworks"
C="$HOME/cutover_work/pr/cycle$N"; mkdir -p "$C"
MAP="$REPO/.migration/03_mapping_spec.json"; TOL="$REPO/.migration/02_tolerances.json"; CAN="$REPO/.migration/canonicalization.json"
COMMON=(--tolerances "$TOL" --canonicalization "$CAN" --mode live --target-uri-secret MONGODB_ATLAS_URI \
        --target-db ow_tp_mongodb_205236 --seed 714559852 --param batch_no=85559852 --param source_ns=demo)
cd "$REPO"
: > "$C/steps.jsonl"
step() { # name cmd...
  local name=$1; shift
  local t0=$(date +%s.%N)
  echo "[$(date -u +%FT%TZ)] START $name"
  "$@" > "$C/$name.log" 2>&1; local rc=$?
  local t1=$(date +%s.%N)
  local wall=$(python3 -c "print(round($t1-$t0,1))")
  echo "[$(date -u +%FT%TZ)] END   $name rc=$rc wall=${wall}s :: $(grep -m1 -E '^recon (PASS|FAIL)|guards (PASS|FAIL)|load complete|docs, indexes' "$C/$name.log" | cut -c1-160)"
  echo "{\"step\":\"$name\",\"rc\":$rc,\"wall_s\":$wall,\"start_utc\":\"$(date -u -d @${t0%.*} +%FT%TZ)\",\"end_utc\":\"$(date -u -d @${t1%.*} +%FT%TZ)\"}" >> "$C/steps.jsonl"
  [ $rc -ne 0 ] && { echo "  !! non-zero: $name"; tail -15 "$C/$name.log" | sed 's/^/     /'; }
  return 0
}
echo "cycle $N start $(date -u +%FT%TZ) head=$(git rev-parse HEAD)" | tee "$C/cycle_start.txt"
step source_pre   $PY "$HOME/cutover_work/pr/source_check.py" "$C/source_pre.json"
if [ "$RESET" = "reset" ]; then
  step reset_U6 $PY scripts/tp_mongo/load_replay_u6.py --report "$C/U6.reset_load_report.json"
  step reset_U7 $PY scripts/tp_mongo/load_u7.py         --report "$C/U7.reset_load_report.json"
  step reset_U8 $PY scripts/tp_mongo/load_u8.py         --report "$C/U8.reset_load_report.json"
  step reset_U9 $PY scripts/tp_mongo/load_replay_u9.py  --report "$C/U9.reset_load_report.json"
fi
# U0-U2, U5: stock harness `recon run`, unit projection of the frozen spec
for U in U0 U1 U2 U5; do
  mkdir -p "$C/$U"
  $PY "$HOME/cutover_work/pr/subset.py" "$MAP" $U "$C/$U/mapping_${U,,}_subset.json" > "$C/$U/subset.txt"
  step "$U" recon run --unit $U --family oracle --mapping "$C/$U/mapping_${U,,}_subset.json" \
       --source-dsn-secret OW_BILLING_FIXTURE_DSN "${COMMON[@]}" --out "$C/$U/gate"
done
# U3: postgres adapter; U4: dynamodb adapter (recon_ext, D13)
mkdir -p "$C/U3" "$C/U4"
step U3 $PY .migration/recon_ext/recon_pg.py --unit U3 --family postgres --mapping "$MAP" --unit-only \
     --source-dsn-secret OW_PG_DSN "${COMMON[@]}" --out "$C/U3/gate"
step U4 $PY .migration/recon_ext/run_dynamo_recon.py --unit U4 --mapping "$MAP" \
     --source-endpoint-secret AWS_ENDPOINT_URL "${COMMON[@]}" --out "$C/U4/gate"
# U6-U9: Tier-4 transcript-replay drivers (recon_ext / scripts)
mkdir -p "$C/U6" "$C/U7" "$C/U8" "$C/U9"
# U6's committed driver writes its artefacts into .migration/recon/U6 regardless of --out (fixed paths);
# run it verbatim, then copy the artefacts out and restore the checked-in files.
step U6 $PY scripts/tp_mongo/recon_u6.py --out "$C/U6/gate"
mkdir -p "$C/U6/gate" && for f in result.json report.md recon.summary.md tier4_replay.json; do cp -f ".migration/recon/U6/$f" "$C/U6/gate/" 2>/dev/null; done
cp -f .migration/recon/U6/mapping/u6.json "$C/U6/gate/mapping_u6.json" 2>/dev/null
git -C "$REPO" checkout -q -- .migration/recon/U6 && git -C "$REPO" clean -fdq .migration/recon/U6
step U7 $PY .migration/recon_ext/recon_u7.py --unit U7 --mapping "$MAP" --source-dsn-secret OW_BILLING_FIXTURE_DSN "${COMMON[@]}" --out "$C/U7/gate"
step U8 $PY .migration/recon_ext/recon_u8.py --unit U8 --mapping "$MAP" --source-dsn-secret OW_BILLING_FIXTURE_DSN "${COMMON[@]}" --out "$C/U8/gate"
step U9 $PY .migration/recon_ext/recon_u9.py --unit U9 --mapping "$MAP" --source-dsn-secret OW_BILLING_FIXTURE_DSN "${COMMON[@]}" --out "$C/U9/gate"
step guards       $PY "$HOME/cutover_work/pr/guards.py" "$C"
step source_post  $PY "$HOME/cutover_work/pr/source_check.py" "$C/source_post.json"
echo "cycle $N end $(date -u +%FT%TZ)" | tee "$C/cycle_end.txt"
git -C "$REPO" status --short > "$C/git_status_after.txt"
