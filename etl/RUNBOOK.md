# ETL cutover and rollback runbook: cron to Airflow

How each of the five legacy cron scripts moves to its Airflow DAG, how it goes back to cron,
who owns it while both exist, and when the legacy script is deleted. Written for the real ETL
EC2 box (`/opt/etl`, the ETL user's crontab). It is rehearsed on the local Compose stack
(LocalStack 3.8, Postgres, MeiliSearch from `docker-compose.infra.yml`, Airflow and the
`legacy-etl-cron` service from `docker-compose.airflow.yml`); every box step has a local
equivalent in [§8](#8-local-rehearsal-compose). **No step in a rehearsal touches an AWS account.**

Target design: [`ETL_UPGRADE_GUIDE.md`](ETL_UPGRADE_GUIDE.md). Connections and Variables:
[`airflow/CONFIG.md`](airflow/CONFIG.md). Legacy cron coexistence:
[`legacy-cron/README.md`](legacy-cron/README.md). Characterization goldens:
[`tests/golden/README.md`](tests/golden/README.md).

Stacked on open PRs: this branch has the Airflow scaffold and `legacy-etl-cron` (#1909).
`airflow/CONFIG.md`, `.env.example` and `make airflow-config-check` come from #1908; the shared
DAG library `otterworks_etl.common` (`otterworks_dag_kwargs`, `LEGACY_SCHEDULES`,
`legacy_run_date`, `log_task_failure`) and `etl/airflow/scripts/run-tests.sh` from #1910. The
DAGs themselves arrive with their own PRs; commands below use their planned ids and schedules.

| Script (`etl/scripts/`) | DAG id | Schedule (UTC) | Kind | Writes / mutates | Destructive |
| --- | --- | --- | --- | --- | --- |
| `analytics_daily.py` | `otterworks_analytics_etl` | `0 2 * * *` | daily | consumes and **deletes SQS messages**; `analytics/daily/year=/month=/day=/{summary.json.gz,hourly_breakdown.json.gz,top_users.jsonl.gz}`, `reports/analytics/daily/<ds>/report.json` in the data lake; upserts `analytics_daily_summary` | SQS messages are consumed |
| `audit_archive_weekly.py` | `otterworks_audit_archive` | `0 3 * * 0` | weekly (Sun) | `audit-archive/year=<yyyy>/week=<ds>/audit_events.jsonl.gz` (GLACIER) and `reports/compliance/audit-archive/<ds>/report.json` in the archive bucket; DynamoDB deletes **only when `audit_archive_delete_enabled=true`** | yes, with the delete flag on |
| `search_reindex_weekly.py` | `otterworks_search_reindex` | `0 4 * * 0` | weekly (Sun) | deletes and recreates the MeiliSearch `documents` and `files` indexes | search is empty while it runs |
| `storage_cleanup_daily.py` | `otterworks_storage_cleanup` | `30 2 * * *` | daily | **moves** orphans from file storage to `otterworks-file-quarantine/quarantined/<ds>/<key>`; `reports/storage-cleanup/<ds>/report.json` | yes, objects leave file storage |
| `user_activity_daily.py` | `otterworks_user_activity_report` | `0 5 * * *` | daily | `reports/user-activity/{<ds>,latest}/activity_report.json`, `reports/user-activity/<ds>/user_summaries.jsonl` | no |

`<ds>` is the UTC day the run **fires** (legacy `datetime.now(tz=timezone.utc)`). The DAGs keep
that date with `legacy_run_date(context)` from `otterworks_etl.common`; it is *not* Airflow's
`ds`, which is one interval earlier. When you look for a run's outputs, use the fire date.

---

## 1. Cutover order

One DAG at a time. Do not start the next until the previous one has had at least one successful
scheduled run and its outputs check out.

1. **`otterworks_analytics_etl`** first. `otterworks_user_activity_report` reads its partitions
   and `analytics_daily_summary`, so analytics must be stable before anything downstream moves.
2. **`otterworks_audit_archive`, alone**, only once its parity report has no failed rows. Cut it
   over with `audit_archive_delete_enabled=false` ([§5.3](#53-otterworks_audit_archive)). Nothing
   else is cut over in the same week.
3. **The other three**, in any order, one per slot: `otterworks_storage_cleanup`
   (`storage_cleanup_normalize_keys=false`), `otterworks_user_activity_report`,
   `otterworks_search_reindex`.

The two behavior flags are **not** part of cutover. Turning either on is its own change after
the DAG has cut over ([§6](#6-follow-up-flags-separate-changes)).

## 2. Conventions used below

```bash
# Airflow CLI. On the deployment: the CLI in the scheduler. Locally:
AF="docker compose -f docker-compose.airflow.yml -p otterworks-airflow exec -T airflow-scheduler airflow"
# AWS CLI. On the box: the ETL instance role. Locally (LocalStack, dummy creds, no account):
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
AWS="aws --endpoint-url http://localhost:4566"
DAG=otterworks_analytics_etl          # the DAG being worked on
SCRIPT=analytics_daily.py             # its legacy script
```

- **Crontab.** The box runs `etl/crontab` as the ETL user's crontab (the lines have no user
  field). Before every edit confirm the box and git agree: `diff <(crontab -l) /opt/etl/crontab`
  must print nothing. Every crontab change is a commit to `etl/crontab` first, then installed
  with `crontab /opt/etl/crontab`; never edit with `crontab -e` only.
- **Variables come from the environment** (`AIRFLOW_VAR_<KEY>`, see `airflow/CONFIG.md`), and an
  environment value wins over the metadata DB. `airflow variables set` on an env-backed key
  writes the DB, logs *"defined in the EnvironmentVariablesBackend … takes precedence"*, and
  changes nothing. Change a Variable by changing its configured value (locally
  `etl/airflow/.env`, then `make airflow-up`) and confirm with `$AF variables get <key>`.
- **Pause, not delete.** A paused DAG keeps its history; that history is the retirement count.

## 3. Preconditions (every DAG)

All must hold before the cutover window. Record the evidence in the cutover ticket.

- [ ] **Parity report: no failed rows.** The DAG PR's parity report (linked in
      [§7](#7-accepted-differences-and-parity-reports)) compares the DAG against the legacy
      goldens for every scenario of the script; every row is *identical* or *accepted
      difference* with a reason. The legacy side is still green:
      `make etl-golden SCRIPT=<script-without-.py> MODE=check`.
- [ ] **DAG unit and integrity tests green** on the DAG PR's CI and locally:
      `etl/airflow/scripts/run-tests.sh` (DAG bag import, no cycles, `dag_id`, `schedule` equal
      to `LEGACY_SCHEDULES[dag_id]`, `catchup=False`, `max_active_runs=1`, failure callback set),
      and `make airflow-check` reports zero import errors.
- [ ] **Connections and Variables present** in the target Airflow:
      `make airflow-config-check` locally; on the deployment
      `$AF connections get <id>` / `$AF variables get <key>` for each entry the DAG uses in
      `airflow/CONFIG.md`. `audit_archive_delete_enabled` must read `false` and
      `storage_cleanup_normalize_keys` must read `false`.
- [ ] **DAG is deployed and paused.** `$AF dags list -o plain | grep $DAG` shows `paused True`.
      DAGs are created paused (`dags_are_paused_at_creation`); if it is unpaused, pause it now
      and check `$AF dags list-runs -d $DAG` for runs you did not expect.
- [ ] **Cron is still healthy** for this script: its last cron log
      (`/var/log/etl/<name>.log`) ends without `FATAL`/`ERROR`, and box crontab equals git.
- [ ] **Owner on hand** for the slot ([§4](#4-ownership-and-alerting)).

## 4. Ownership and alerting

- **Owner and contact:** data team, `data-team@otterworks.dev` (named in `etl/crontab`; the
  crontab adds "Jake left in 2020, ask Sarah"). DAG `owner` is `otterworks-data`.
- **Cron (until a script is retired):** stdout/stderr append to the log named on its crontab line,
  `/var/log/etl/{analytics,audit,search,storage,activity}.log` on the box. There is no alerting;
  someone has to read the log. Locally the same lines go to the `legacy-etl-cron` container's
  stdout (`docker compose -f docker-compose.airflow.yml -p otterworks-airflow logs legacy-etl-cron`).
- **Airflow task logs:** per try, in the Airflow UI (DAG → Grid → task → Logs), stored under the
  scheduler/worker `logs/dag_id=<dag>/run_id=<run>/task_id=<task>/attempt=<n>.log`. Locally the UI
  is `http://localhost:8280`.
- **Failure callback:** every task has `on_failure_callback=log_task_failure`
  (`otterworks_etl.common`, via `otterworks_dag_kwargs`). After the last of 3 retries
  (5 min, exponential backoff) it writes one structured `ERROR` line `event=task_failed` with
  `dag_id`, `task_id`, `run_id`, `logical_date`, `try_number`, `max_tries`, `exception_type`,
  `exception` and `log_url` (deep link to the failing try's log) to the **scheduler's/worker's
  process log** (locally `docker compose ... logs airflow-scheduler | grep task_failed`), and
  marks the run failed in the UI. Email/Slack/PagerDuty routing on that event is not wired yet;
  until it is, the owner checks the DAG's run state after each slot during coexistence.

## 5. Per-DAG procedure

### 5.0 Cutover, common steps (pause-safe, no double run)

The risk is one slot run twice (cron and Airflow), or Airflow back-running a slot cron already
ran. A double analytics run consumes and deletes SQS messages in the first run and then
overwrites that day's partition and `analytics_daily_summary` row without them; a double storage
cleanup overwrites the day's report with smaller counts; a double reindex empties search twice.

**Pick the boundary.** `LAST` = the last slot cron runs; `FIRST` = the next slot after it, the
first one Airflow runs. Cut over between them, not within minutes of either.

**Set `start_date` so the first scheduled run fires at `FIRST`.** Airflow fires a run at the
*end* of its interval, so with `catchup=False` the first run fires one slot after `start_date`:

| `start_date` (with `catchup=False`) | first run fires at | effect |
| --- | --- | --- |
| `LAST` (the slot cron has just run) | `FIRST` | **correct** |
| `FIRST` | the slot after `FIRST` | one slot is skipped |
| any date before `LAST` (e.g. the code default) | **immediately on unpause** (for the latest past slot) | double run of `LAST` |

Measured on Airflow 2.8.4 at 2026-10-07T15:24Z (see the PR for the probe): daily `0 2 * * *`
with `start_date=2026-10-07T02:00Z` fires at `2026-10-08T02:00Z`; with `2026-10-08T02:00Z` it fires
at `2026-10-09T02:00Z`; with `2026-01-01` it is due at once (`2026-10-07T02:00Z`). Weekly
`0 3 * * 0` with `start_date=2026-10-04T03:00Z` fires at `2026-10-11T03:00Z`. In other words, "start
at the next slot" means *the first run is at the next slot*; set `start_date` to `LAST`.

1. **Release the DAG with its cutover `start_date`.** In the DAG module set
   `start_date=<LAST>` (`pendulum.datetime(..., tz="UTC")`) and keep `catchup=False` (both from
   the DAG PR / `otterworks_dag_kwargs`). Deploy. The DAG stays **paused**.
2. **Confirm what Airflow will do before unpausing:**
   ```bash
   $AF dags list -o plain | grep "$DAG"     # paused True
   $AF dags next-execution "$DAG"           # prints the LOGICAL date = LAST (interval start);
                                            # the run itself fires at FIRST
   $AF dags list-runs -d "$DAG" --no-backfill   # nothing scheduled/running
   ```
   If `next-execution` prints anything earlier than `LAST`, stop: `start_date` is wrong and
   unpausing would run a slot cron already ran.
3. **Remove the script's crontab line** (only that line) and install it:
   ```bash
   sed -i "/run.sh $SCRIPT /d" etl/crontab && git diff etl/crontab     # exactly one line removed
   git commit -m "etl: cut $SCRIPT over to $DAG (crontab line removed)" etl/crontab
   # on the box, after deploying the commit:
   crontab /opt/etl/crontab && diff <(crontab -l) /opt/etl/crontab && ! crontab -l | grep -F "$SCRIPT"
   ```
   From here until step 4, neither side runs this script: there is no window with both.
4. **Unpause:** `$AF dags unpause "$DAG"` (prints `paused: False`). `list-runs` must still show
   no run until `FIRST`. If one appears with an earlier logical date, pause, mark it failed
   (UI → run → Mark failed) before its tasks write, and fix `start_date`.
5. **Watch `FIRST`:** in the UI (Grid view) the run `scheduled__<LAST>` starts at `FIRST`, every
   task is green; no `task_failed` event in the scheduler log. Then check the outputs for
   `<ds>` = the date of `FIRST` (per DAG below), compared with the last cron run's outputs.
6. **Record** `LAST`, `FIRST`, the run id and the output check in the ticket; the retirement count
   ([§9](#9-retirement-after-one-weekly-cycle)) starts with this run.

### 5.1 Rollback to cron, common steps

Roll back when a scheduled run fails and cannot be fixed before the next slot, or outputs are
wrong. Order matters: Airflow stops first, so the slot never has two owners.

1. **Pause the DAG:** `$AF dags pause "$DAG"`. If a run is in progress, let the current task
   finish or mark the run failed in the UI; then confirm `$AF dags list-runs -d "$DAG" --state running`
   prints `No data found`.
2. **Restore the crontab line from git**, unchanged:
   ```bash
   git log --oneline -- etl/crontab                         # find the cutover commit
   git revert --no-edit <cutover-commit>                    # restores exactly that line
   # on the box, after deploying the commit:
   crontab /opt/etl/crontab && diff <(crontab -l) /opt/etl/crontab && crontab -l | grep -F "$SCRIPT"
   ```
3. **Confirm the runtime cron needs is still on the box:**
   ```bash
   test -x /opt/etl/run.sh && test -f "/opt/etl/scripts/$SCRIPT"
   test -s /opt/etl/config.ini && python3 -c 'import configparser as c; p=c.ConfigParser(); p.read("/opt/etl/config.ini"); print(sorted(p.sections()))'
   # expect ['aws', 'database', 's3', 'services'] (sections only, never print values)
   ls -l /opt/etl/.env 2>/dev/null || true                  # optional, sourced by run.sh
   ```
   The box-local `config.ini` is the only copy of the real values; the committed `etl/config.ini`
   is not it. If it is missing, stop and get it restored before the next slot.
4. **Do the destructive-script checks** for this DAG (5.3 audit, 5.4 storage) **before**
   re-running anything for the failed day.
5. **Catch up the missed day, if needed, by cron only:** `/opt/etl/run.sh $SCRIPT >> /var/log/etl/<name>.log 2>&1`
   once. Never `$AF dags trigger` and cron for the same day.
6. **Restart the retirement count** at zero for this DAG ([§9](#9-retirement-after-one-weekly-cycle))
   and note the rollback in the ticket. Cut over again with §5.0 once fixed.

### 5.2 `otterworks_analytics_etl`

- **Slots:** daily `02:00`. Cut over first ([§1](#1-cutover-order)).
- **Output check for `<ds>`:** in `otterworks-data-lake`,
  `analytics/daily/year=YYYY/month=MM/day=DD/{summary.json.gz,hourly_breakdown.json.gz,top_users.jsonl.gz}`
  and `reports/analytics/daily/<ds>/report.json` exist; `analytics_daily_summary` has a row for
  `report_date = '<ds>'` (`psql ... -c "select * from analytics_daily_summary where report_date='<ds>'"`);
  the `otterworks-analytics` queue is drained (`ApproximateNumberOfMessages` back near zero).
- **Rollback note:** SQS messages a failed DAG run already deleted are gone; a re-run for that
  day only sees DynamoDB events and the remaining messages, and overwrites the partition and
  upserts the row (`ON CONFLICT (report_date)`). Note the lower counts in the ticket rather than
  re-running more than once.

### 5.3 `otterworks_audit_archive`

Cut over **alone**, with parity green and **`audit_archive_delete_enabled=false`**. That matches
legacy, which never deletes: it builds the delete key as `{event_id, timestamp}`, the table is
keyed on `id`, every delete fails, and it reports `events_deleted_from_source: 0`. With the flag
`false` the DAG archives and reports exactly as legacy and leaves DynamoDB untouched.

- **Slots:** Sunday `03:00`. `LAST` = the Sunday cron runs, `start_date=<LAST>`, first DAG run
  the following Sunday.
- **Precondition extra:** `$AF variables get audit_archive_delete_enabled` → `false`.
- **Output check for `<ds>`:**
  ```bash
  $AWS s3api head-object --bucket otterworks-audit-archive --key "audit-archive/year=${DS:0:4}/week=$DS/audit_events.jsonl.gz" --query StorageClass   # "GLACIER"
  $AWS s3 cp "s3://otterworks-audit-archive/reports/compliance/audit-archive/$DS/report.json" - | jq '.results'
  ```
  `events_archived` matches the cron run's count over the same table state, and
  `events_deleted_from_source` is `0`. The item count of `otterworks-audit-events` did not drop.
- **Rollback, before re-running anything:**
  1. Was the delete flag on for any DAG run? Check each run's compliance report
     `events_deleted_from_source`. If it is non-zero, DynamoDB lost those events; their only copy
     is that run's archive object. Do not re-run anything until it is verified (6.1 pre-check 3).
  2. A re-run for the same `<ds>` (cron or DAG) **overwrites** `audit-archive/year=<yyyy>/week=<ds>/audit_events.jsonl.gz`
     and the report. After a delete-enabled run the re-run scans fewer events and would replace
     the archive with a smaller one. Copy both objects aside first:
     `$AWS s3 cp s3://otterworks-audit-archive/<key> s3://otterworks-audit-archive/rollback/<date>/<key>`
     (the archive is GLACIER: `restore-object` it first, see 6.1 pre-check 3).
  3. Legacy itself deletes nothing, so once 1 and 2 are done the cron re-run is safe.

### 5.4 `otterworks_storage_cleanup`

Cut over with **`storage_cleanup_normalize_keys=false`**: exact-string matching of metadata
`s3_key` against object keys, as legacy.

- **Slots:** daily `02:30`.
- **Precondition extra:** `$AF variables get storage_cleanup_normalize_keys` → `false`.
- **Output check for `<ds>`:**
  ```bash
  $AWS s3 cp "s3://otterworks-data-lake/reports/storage-cleanup/$DS/report.json" - | jq '.orphans, .cleanup'
  $AWS s3 ls "s3://otterworks-file-quarantine/quarantined/$DS/" --recursive | wc -l   # = objects_quarantined
  ```
  `objects_failed` is `0`; `objects_quarantined` is in line with recent cron reports (a sudden
  jump means references stopped matching; pause and investigate before the next slot).
- **Rollback, before re-running anything:**
  1. The objects a DAG run moved are in `otterworks-file-quarantine/quarantined/<ds>/<key>`,
     not in file storage. A re-run does not bring them back; it quarantines only what is
     orphaned now. If the moves were wrong, restore them first ([§6.2](#62-storage_cleanup_normalize_keys)).
  2. A re-run for the same `<ds>` overwrites `reports/storage-cleanup/<ds>/report.json` with
     smaller counts, and overwrites any quarantine copy at the same `<ds>/<key>`. Copy the report
     aside first (`$AWS s3 cp ... reports/storage-cleanup/<ds>/report.json ./storage-<ds>-report.json`).
  3. If the DAG ran with `storage_cleanup_normalize_keys=true`, rolling back to cron brings back
     exact matching: the next cron run quarantines files referenced as `/files/...` or
     `s3://.../files/...` again. That is legacy behavior; restore them afterwards if needed.

### 5.5 `otterworks_user_activity_report`

- **Slots:** daily `05:00`; after analytics has cut over and is stable.
- **Output check for `<ds>`:** `reports/user-activity/<ds>/activity_report.json`,
  `reports/user-activity/<ds>/user_summaries.jsonl` and `reports/user-activity/latest/activity_report.json`
  exist in `otterworks-data-lake`, and `latest` equals the `<ds>` report.
- **Rollback note:** not destructive; a re-run overwrites the `<ds>` and `latest` reports.

### 5.6 `otterworks_search_reindex`

- **Slots:** Sunday `04:00`.
- **Output check:** `GET /indexes/documents/stats` and `GET /indexes/files/stats` on MeiliSearch
  return `numberOfDocuments` equal to the document-service and file-service totals (the script's
  own validation, which fails the run on mismatch); search in the app returns results.
- **Rollback note:** the run deletes and recreates both indexes, so search is empty while it
  runs. Never let cron and the DAG overlap; after a failed DAG run, re-run once by cron to rebuild.

## 6. Follow-up flags (separate changes)

Neither flag is turned on during cutover. Each is its own reviewed change to the configured
Variable value, made after the DAG has cut over and with the sign-off below. A flag change does
not restart the retirement count unless it leads to a rollback.

### 6.1 `audit_archive_delete_enabled`

`true` turns on the new delete by `id` of every event the run archived. **Prerequisite:
compliance signs off on the 90-day retention**, having reviewed the two items in 6.1.1.

> **Warning.** Legacy has never deleted anything. The first enabled run archives and then
> **deletes every event older than 90 days ever accumulated in `otterworks-audit-events`**, not
> one week's worth. Run it in a quiet window, expect it to take long and to consume write
> capacity, and keep its archive object until compliance has verified it.

**Pre-check, the week of enabling** (all against the table state just before the slot):

1. Sign-off recorded (ticket link), including 6.1.1.
2. Count the candidates with the run's filter (cutoff = `<ds> - 90 days`, `YYYY-MM-DDT00:00:00Z`):
   ```bash
   CUTOFF=$(date -u -d "$DS -90 days" +%Y-%m-%dT00:00:00Z)
   $AWS dynamodb scan --table-name otterworks-audit-events --select COUNT \
     --filter-expression '#ts < :c' --expression-attribute-names '{"#ts":"timestamp"}' \
     --expression-attribute-values "{\":c\":{\"S\":\"$CUTOFF\"}}"
   ```
3. **Archive present and verified for those keys.** Every `id` that will be deleted must be in
   an archive object. Run the DAG with the flag still `false` for the slot before enabling (it
   archives the same set), then compare:
   ```bash
   KEY="audit-archive/year=${DS:0:4}/week=$DS/audit_events.jsonl.gz"
   # GLACIER (on AWS and on LocalStack 3.8): restore first, wait for Restore: ongoing-request="false"
   $AWS s3api restore-object --bucket otterworks-audit-archive --key "$KEY" --restore-request '{"Days":7,"GlacierJobParameters":{"Tier":"Standard"}}'
   $AWS s3 cp "s3://otterworks-audit-archive/$KEY" - | gunzip | jq -r '.id' | sort -u > archived_ids
   $AWS dynamodb scan --table-name otterworks-audit-events --projection-expression id \
     --filter-expression '#ts < :c' --expression-attribute-names '{"#ts":"timestamp"}' \
     --expression-attribute-values "{\":c\":{\"S\":\"$CUTOFF\"}}" | jq -r '.Items[].id.S' | sort -u > candidate_ids
   comm -13 archived_ids candidate_ids | wc -l     # must be 0: no candidate missing from the archive
   ```
4. Take an on-demand table backup on the deployment (`aws dynamodb create-backup`) as the
   restore path; the archive is JSON, and DynamoDB numbers that are not integral come back as
   floats (`decimal_values` golden), so it is not a lossless restore.
5. **Partial-delete recovery path in place.** A prerequisite, not yet implemented (#1926 review):
   if `cleanup_dynamodb` deletes some batches and then fails for good, a fresh run or a cleared
   scan/upload scans only the surviving events, the upload guard refuses to overwrite the date's
   archive with that smaller set, and the rest is never deleted or reported. Do not enable until
   the DAG reuses and verifies the existing archive for the same `<ds>` in that case (keeping every
   archived event, adding any new ones, then cleanup and report from it, including an empty scan).
   Until then a task retry of `cleanup_dynamodb` alone is the only safe resume.

**Enable:** change the configured value to `true`, deploy, `$AF variables get audit_archive_delete_enabled`
→ `true`. After the run: `events_deleted_from_source` equals `events_archived`, and the table
count dropped by that number.

**Switch off:** change the configured value back to `false` and redeploy before the next Sunday
slot; confirm with `$AF variables get`. If a delete-enabled run is in progress and must stop,
pause the DAG and mark the running delete task failed in the UI; what it already deleted is in
that run's archive object (keep it, 5.3 rollback).

#### 6.1.1 Flagged for compliance (reproduced at cutover, review before enabling deletes)

- **The cutoff is a string comparison** (`#ts < :cutoff`, inherited from legacy, pinned by the
  `cutoff_boundary` golden). Timestamps are compared as text, not instants: `.000Z`, `+00:00`
  and date-only spellings of the cutoff instant are archived; a `-05:00` offset that is *after*
  the cutoff is archived; lowercase `z` on the cutoff is kept; numeric (epoch) timestamps and
  items without `timestamp` are **never archived**, so with deletes on they are retained forever.
  With deletes on, mis-formatted events are deleted early or never.
- **The compliance report's `compliance` block is hardcoded `true`:** `gdpr_compliant`,
  `soc2_compliant`, `data_encrypted_at_rest`, `data_encrypted_in_transit`. Nothing is checked;
  the DAG writes the same values for parity. The report must not be used as evidence of
  compliance until these are computed or removed.
- Related: an old item without `event_id` makes legacy exit 1 after uploading the archive and
  before the report (`missing_event_id` golden). How the DAG treats it is in its parity report.
- **Follow-up: live audit-service events use `Timestamp`, not `timestamp`.** `SaveEventAsync`
  (`services/audit-service/src/Services/DynamoDbAuditRepository.cs`) writes the capitalized
  attribute; legacy and the DAG filter on lowercase `timestamp` (kept for cutover parity), and
  DynamoDB attribute names are case-sensitive, so service-written events are never archived and,
  with deletes on, never deleted. A known gap carried over from legacy. The fix (archive and
  delete on either attribute, using one value for both the filter and the retention check) is its
  own change, alongside this flag.

### 6.2 `storage_cleanup_normalize_keys`

`true` normalizes metadata `s3_key` values before matching (decision `d-storage-key-match`):

- references with a **leading `/`** (`/files/user-bob/leading.txt`) or an **`s3://` prefix**
  (`s3://otterworks-file-storage/files/user-carol/uri.txt`) **stop being quarantined**: they now
  match their object;
- **case variants are still quarantined** (`files/user-alice/report.pdf` does not match
  `files/user-alice/Report.PDF`);
- everything else is unchanged (`reference_mismatches` golden: the parity report shows these rows
  as accepted differences for the flag-on run).

**Enable:** change the configured value to `true`, deploy, confirm
`$AF variables get storage_cleanup_normalize_keys` → `true`, and before the next slot restore
the files that exact matching quarantined wrongly (below). Expect `objects_quarantined` to drop
in the next report.

**Restore wrongly quarantined files** (`otterworks-file-quarantine/<prefix>/<ds>/<key>` →
`otterworks-file-storage/<key>`; `<prefix>` is `storage_cleanup_quarantine_prefix`,
`quarantined`). Do this with the flag already `true`, otherwise the next run moves them again.

```bash
# 1. References that only match after normalization (the wrongly quarantined set)
$AWS dynamodb scan --table-name otterworks-file-metadata --projection-expression s3_key \
  | jq -r '.Items[].s3_key.S // empty' | grep -E '^(/|s3://)' \
  | sed -E 's#^s3://[^/]+/##; s#^/+##' | sort -u > keys_to_restore
# 2. Find each key's quarantine copy <prefix>/<ds>/<key> (newest <ds> wins) and copy it back
P=quarantined
$AWS s3api list-objects-v2 --bucket otterworks-file-quarantine --prefix "$P/" \
  | jq -r '.Contents[]?.Key' > quarantined_keys
while IFS= read -r KEY; do
  SRC=$(awk -v p="$P/" -v k="$KEY" 'index($0, p) == 1 && substr($0, length(p) + 12) == k' quarantined_keys | sort | tail -1)
  [ -n "$SRC" ] || { echo "NOT QUARANTINED: $KEY"; continue; }
  if $AWS s3api head-object --bucket otterworks-file-storage --key "$KEY" >/dev/null 2>&1; then
    echo "SKIP exists in file storage: $KEY"; continue      # never overwrite a newer upload
  fi
  $AWS s3api copy-object --bucket otterworks-file-storage --key "$KEY" \
    --copy-source "otterworks-file-quarantine/$SRC" --metadata-directive COPY >/dev/null \
    && echo "RESTORED $SRC -> $KEY"
done < keys_to_restore
# 3. Verify: ContentLength/ETag equal on both sides; keep the quarantine copy until the next
#    cleanup report no longer lists the key, then it may be removed.
```

Compare `ContentLength` and `ContentType` on both sides; for single-part objects the ETag
matches too (a multipart object's ETag changes on copy, compare a download hash instead).

**Switch off:** change the configured value back to `false` and redeploy before the next 02:30
slot; confirm with `$AF variables get`. The next run quarantines the `/` and `s3://` references
again (legacy behavior); if they were restored, they move back to quarantine and can be restored
again after the next enable.

## 7. Accepted differences and parity reports

Each DAG PR carries the parity report for its script: every golden scenario, legacy (before)
against the DAG (after), each row *identical*, *accepted difference* (with reason) or *failed*.
Cutover needs no failed rows. Rows below are the differences already decided; the report is
authoritative and may add rows.

| DAG | Parity report | Compared | Before (legacy) | After (DAG) | Result |
| --- | --- | --- | --- | --- | --- |
| `otterworks_analytics_etl` | to be added per DAG PR | all `analytics_daily` scenarios (`smoke`, `full_day`, `dynamodb_only`, `empty_input`, `no_events_for_ds`, `postgres_unavailable`, `rerun_upsert`, `sqs_non_object_body`) | goldens | DAG run | to be filled by the DAG PR |
| `otterworks_analytics_etl` | to be added per DAG PR | SQS queue | hardcoded real-AWS URL with an account id | `analytics_sqs_queue_name` resolved per environment | accepted difference: config, not behavior (`airflow/CONFIG.md`) |
| `otterworks_audit_archive` | to be added per DAG PR | all `audit_archive_weekly` scenarios (`smoke`, `cutoff_boundary`, `decimal_values`, `empty_table`, `missing_event_id`, `multi_batch`, `no_old_events`) | goldens | DAG run, `audit_archive_delete_enabled=false` | to be filled by the DAG PR |
| `otterworks_audit_archive` | to be added per DAG PR | DynamoDB after the run, flag `false` | nothing deleted (wrong key), `events_deleted_from_source: 0` | nothing deleted, `0` | identical |
| `otterworks_audit_archive` | to be added per DAG PR | DynamoDB after the run, flag `true` | nothing deleted | archived events deleted by `id` | accepted difference, **not enabled at cutover** (6.1, compliance sign-off) |
| `otterworks_audit_archive` | to be added per DAG PR | cutoff comparison; `compliance` block | string compare; hardcoded `true` | same | identical, **flagged for compliance** (6.1.1) |
| `otterworks_search_reindex` | to be added per DAG PR | all `search_reindex_weekly` scenarios (`smoke`, `duplicate_ids`, `empty_upstreams`, `failing_page`, `invalid_document_id`, `pagination`) | goldens | DAG run | to be filled by the DAG PR |
| `otterworks_storage_cleanup` | to be added per DAG PR | all `storage_cleanup_daily` scenarios (`smoke`, `empty_storage`, `no_orphans`, `paginated_listing`, `quarantine_failure`, `reference_mismatches`) | goldens | DAG run, `storage_cleanup_normalize_keys=false` | to be filled by the DAG PR |
| `otterworks_storage_cleanup` | to be added per DAG PR | `reference_mismatches`, flag `false` | `/` and `s3://` and case variants quarantined | same | identical |
| `otterworks_storage_cleanup` | to be added per DAG PR | `reference_mismatches`, flag `true` | `/` and `s3://` variants quarantined | not quarantined; case variants still quarantined | accepted difference, **not enabled at cutover** (6.2) |
| `otterworks_user_activity_report` | to be added per DAG PR | all `user_activity_daily` scenarios (`smoke`, `empty`, `lookback_window`, `malformed_inputs`, `postgres_unavailable`, `data_lake_bucket_missing`, `top_users_truncation`) | goldens | DAG run | to be filled by the DAG PR |

When a DAG PR lands, replace its "to be added per DAG PR" with the link to its parity report.

## 8. Local rehearsal (Compose)

Exercise this runbook (plan step s4.2) end to end on the session machine. No AWS credentials,
no cloud endpoints: `aws` only ever talks to `http://localhost:4566` (LocalStack).

| Box step | Local equivalent |
| --- | --- |
| infra | `docker compose -f docker-compose.infra.yml up -d --wait postgres localstack meilisearch` |
| Airflow up / health | `make airflow-up` (UI `http://localhost:8280`), `make airflow-check`, `make airflow-config-check` |
| cron running `etl/crontab` | `make legacy-cron-up` (renders a dev-only `config.ini`; the committed `etl/config.ini` is not used) |
| `crontab /opt/etl/crontab` after removing/restoring a line | edit `etl/crontab` (or point `LEGACY_ETL_CRONTAB` at a copy), then `make legacy-cron-reload` |
| `/opt/etl/run.sh <script>` once | `make legacy-cron-run SCRIPT=<script-without-.py>` (exit 3 if its line was removed: cut over) |
| `/var/log/etl/*.log` | `docker compose -f docker-compose.airflow.yml -p otterworks-airflow logs legacy-etl-cron` |
| wait for the next slot | `$AF dags trigger $DAG` only in a rehearsal, with cron's line removed; a scheduled run is still needed to rehearse `start_date` |
| teardown | `make legacy-cron-down`, `make airflow-down` |

Rehearse in the order of [§1](#1-cutover-order): cut analytics over, roll it back, cut it over
again; then audit archive with the flag `false`; then the other three. For 6.1 and 6.2 seed the
`cutoff_boundary` / `reference_mismatches` scenarios (`make etl-golden ... SCENARIO=`) and run the
pre-check and restore commands against LocalStack.

## 9. Retirement after one weekly cycle

A legacy script stays in `etl/scripts/` (and on the box) for one full weekly cycle after its DAG
cuts over, so rollback (§5.1) stays one revert away.

- **Daily DAG** (`otterworks_analytics_etl`, `otterworks_storage_cleanup`,
  `otterworks_user_activity_report`): **seven consecutive successful scheduled runs**.
- **Weekly DAG** (`otterworks_audit_archive`, `otterworks_search_reindex`): **one successful
  scheduled run**.
- **Any rollback restarts the count at zero.** Manual triggers and backfills do not count; a
  failed scheduled run breaks the sequence (retries that end in success are fine).

### 9.1 Checklist: cycle complete (per DAG)

- [ ] `$AF dags list-runs -d $DAG --no-backfill -o plain` (newest first): the latest 7 (daily) /
      1 (weekly) runs are `scheduled__…`, `success`, on consecutive slots, the first of them at
      or after the cutover `FIRST`, with no failed or skipped slot in between.
- [ ] No rollback since the first counted run: `git log --oneline -- etl/crontab` shows the
      cutover commit as the last change touching `$SCRIPT`, and `crontab -l | grep -cF "$SCRIPT"` is `0` on the box.
- [ ] Each counted run's outputs exist for its `<ds>` (per-DAG check in §5).
- [ ] No `event=task_failed` for `$DAG` in the scheduler log since the first counted run except
      tries that were retried to success.
- [ ] The DAG PR's parity report is linked in §7 and still has no failed rows.
- [ ] The DAG and cron each ran on no slot twice (one output set per `<ds>`; cron log has no run
      after the cutover).
- [ ] Owner sign-off in the ticket.

### 9.2 Removing the script

One commit per script, after its checklist passes:

```bash
git rm etl/scripts/$SCRIPT
git commit -m "etl: retire $SCRIPT ($DAG completed one weekly cycle)"
```

Same commit: drop anything that still runs that script (its `legacy-cron` smoke usage and the
legacy side of its golden check; the recorded goldens stay as the DAG's contract). Then remove
`/opt/etl/scripts/$SCRIPT` from the box.

With the **last** script, two more commits, each on its own, after that script's commit:

```bash
git rm etl/run.sh  && git commit -m "etl: remove run.sh (no cron-run scripts left)"
git rm etl/crontab && git commit -m "etl: remove crontab (all ETL schedules run in Airflow)"
```

On the box, after the crontab commit: `crontab -l` has no ETL lines left, then `crontab -r` for
the ETL user (only if it holds nothing else), and remove `/opt/etl/run.sh`. The box-local
`config.ini` and its credentials are retired separately (they back no Airflow Connection).
