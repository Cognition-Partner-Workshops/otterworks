#!/usr/bin/env bash
# End-to-end check of legacy-etl-cron against docker-compose.infra.yml:
#   1. a crontab line fires on its schedule and its /var/log/etl output reaches stdout
#   2. removing that line (cutover) stops it: `run` exits 3, nothing fires
#   3. restoring the line (rollback) makes supercronic schedule and fire it again
# Uses a scratch copy of the pre-cutover crontab (etl/legacy-cron/crontab.pre-cutover) with
# storage_cleanup_daily set to every minute; etl/crontab itself is never touched.
# Expects `make legacy-cron-up` to have run.
set -euo pipefail
cd "$(dirname "$0")/../../.."

COMPOSE=(docker compose -f docker-compose.airflow.yml -p otterworks-airflow --profile legacy-cron)
SCRIPT=storage_cleanup_daily.py
WORK=$(mktemp -d)
trap 'LEGACY_ETL_CRONTAB="" "${COMPOSE[@]}" up -d --force-recreate --wait legacy-etl-cron >/dev/null 2>&1; rm -rf "$WORK"' EXIT

step() { printf '\n== %s\n' "$*"; }
reload() {
  LEGACY_ETL_CRONTAB="$1" "${COMPOSE[@]}" up -d --force-recreate --wait legacy-etl-cron >/dev/null 2>&1
}
logs() { "${COMPOSE[@]}" logs --no-log-prefix legacy-etl-cron 2>&1; }
# supercronic logs the job's own stdout as msg="..." channel=stdout job.command="...".
FIRED="${SCRIPT} completed successfully\" channel=stdout .*job.command=\"/opt/etl/run.sh ${SCRIPT} >> /var/log/etl/storage.log"
wait_fired() {
  for _ in $(seq 1 45); do
    if logs | grep -q "$FIRED"; then break; fi
    sleep 2
  done
  logs | grep -E "job.command=\"/opt/etl/run.sh ${SCRIPT}" | grep -E "starting|completed|job succeeded|golden-shim" | head -6
  logs | grep -q "$FIRED" \
    || { echo "FAIL: ${SCRIPT} did not fire within 90s ($1)" >&2; logs | tail -30 >&2; exit 1; }
}

BASE=etl/legacy-cron/crontab.pre-cutover
# Same lines as the pre-cutover crontab; only the storage_cleanup schedule becomes "* * * * *".
sed -E "s|^[^#].* (/opt/etl/run.sh ${SCRIPT} .*)$|* * * * * \1|" "$BASE" >"$WORK/crontab.fires"
grep -v " ${SCRIPT} " "$BASE" >"$WORK/crontab.cutover"

step "scheduled: ${SCRIPT} every minute"
diff "$BASE" "$WORK/crontab.fires" || true
reload "$WORK/crontab.fires"
wait_fired "first schedule"
echo "PASS: fired on schedule, run.sh output reached container stdout via /var/log/etl/storage.log"

step "cutover: remove the ${SCRIPT} line"
diff "$BASE" "$WORK/crontab.cutover" || true
reload "$WORK/crontab.cutover"
logs | grep "job(s) scheduled"
set +e
"${COMPOSE[@]}" exec -T legacy-etl-cron python3 /opt/legacy-cron/legacy_cron.py run "$SCRIPT"
rc=$?
set -e
[ "$rc" -eq 3 ] || { echo "FAIL: run exited $rc, want 3" >&2; exit 1; }
sleep 65
if logs | grep -q "job.command=\"/opt/etl/run.sh ${SCRIPT}"; then
  echo "FAIL: ${SCRIPT} still fired after its line was removed" >&2; exit 1
fi
echo "PASS: run exits 3 and nothing fired for 65s after the line was removed"

step "rollback: restore the ${SCRIPT} line"
diff "$WORK/crontab.cutover" "$WORK/crontab.fires" || true
reload "$WORK/crontab.fires"
logs | grep "job(s) scheduled"
wait_fired "after rollback"
echo "PASS: line restored, supercronic fired ${SCRIPT} on schedule again"

# etl/crontab is header-only after cutover; full rollback restores the pre-cutover lines.
step "rollback: pre-cutover crontab ($BASE)"
reload "$PWD/$BASE"
logs | grep -q "5 job(s) scheduled" \
  || { echo "FAIL: $BASE did not schedule 5 jobs" >&2; logs | tail -10 >&2; exit 1; }
logs | grep -q "^\[legacy-etl-cron\]   30 2 \* \* \*  /opt/etl/run.sh ${SCRIPT} " \
  || { echo "FAIL: ${SCRIPT} not scheduled at 30 2 * * * from $BASE" >&2; exit 1; }
echo "PASS: $BASE schedules all 5 jobs, ${SCRIPT} back at 30 2 * * *"
