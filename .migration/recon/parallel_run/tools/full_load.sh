#!/usr/bin/env bash
# One full-estate load of every unit's loader from the run-branch head, strictly serial (source-load cap 1).
# Reports are written OUTSIDE the repo. Same invocations as the wave reports.
set -uo pipefail
source "$HOME/cutover_work/pr/env.sh"
REPO="$HOME/cutover_work/otterworks"
OUT="$HOME/cutover_work/pr/load"; mkdir -p "$OUT"
cd "$REPO"
run() { # name cmd...
  local name=$1; shift
  local t0=$(date +%s)
  echo "[$(date -u +%FT%TZ)] START $name"
  "$@" > "$OUT/$name.log" 2>&1; local rc=$?
  local t1=$(date +%s)
  echo "[$(date -u +%FT%TZ)] END   $name rc=$rc wall=$((t1-t0))s"
  echo "{\"unit\":\"$name\",\"rc\":$rc,\"wall_s\":$((t1-t0)),\"start\":\"$(date -u -d @$t0 +%FT%TZ)\",\"end\":\"$(date -u -d @$t1 +%FT%TZ)\"}" >> "$OUT/load_summary.jsonl"
  [ $rc -ne 0 ] && { echo "FAILED: $name"; tail -20 "$OUT/$name.log"; }
  return 0
}
: > "$OUT/load_summary.jsonl"
run U0 $PY scripts/tp_mongo/load_u0.py --report "$OUT/U0.load_report.json"
run U1 $PY scripts/tp_mongo/load_u1.py --report "$OUT/U1.load_report.json"
run U2 $PY scripts/tp_mongo/load_u2.py --report-out "$OUT/U2.load_report.json"
run U3 $PY scripts/tp_mongo/load_u3.py --report "$OUT/U3.load_report.json"
run U4 $PY scripts/tp_mongo/load_u4.py --report "$OUT/U4.load_report.json"
run U5 $PY scripts/tp_mongo/load_u5.py --report "$OUT/U5.load_report.json"
run U6 $PY scripts/tp_mongo/load_replay_u6.py --report "$OUT/U6.load_report.json"
run U7 $PY scripts/tp_mongo/load_u7.py --report "$OUT/U7.load_report.json"
run U8 $PY scripts/tp_mongo/load_u8.py --report "$OUT/U8.load_report.json"
run U9 $PY scripts/tp_mongo/load_replay_u9.py --report "$OUT/U9.load_report.json"
echo DONE
