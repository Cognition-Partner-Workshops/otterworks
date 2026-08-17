# Cron activity

This unit rewrites `etl/scripts/user_activity_daily.py`. The extractor backfills
pre-run-date history into the `ow_tp` landing volume; the daily job consumes the
cron-analytics gold tables and publishes an idempotent activity report.

## Parent migration commands

```sh
NS=demo DS=2026-01-15
PYTHON=$(scripts/tp_cronbox/ensure_venv.sh)
AWS_ENDPOINT_URL=http://localhost:4566 "$PYTHON" scripts/tp_cron_activity/extract_history.py --ns "$NS" --ds "$DS" --target databricks
cd infrastructure/databricks/cronbox
DATABRICKS_HOST=${DATABRICKS_DEMO_HOST} DATABRICKS_TOKEN=${DATABRICKS_DEMO_TOKEN} mise exec -- databricks bundle deploy
cd -
python3 scripts/tp_dbx/run_job.py ow_tp_cron_activity_history_backfill --ns "$NS" --ds "$DS"
python3 scripts/tp_dbx/run_job.py ow_tp_cron_user_activity_daily --ns "$NS" --ds "$DS"
make tp-cron-activity-recon NS="$NS" DS="$DS"
```

## Public gold interface

The unit owns `ow_tp.gold.user_activity_daily`, `user_activity_user_summaries`,
`user_activity_window_coverage`, and the `user_activity_latest` view. All rows
are scoped by `(namespace, report_date)`. The report has the legacy scalar,
trends, daily summaries, ordered user summaries, and top users; `generated_at`
is intentionally omitted because it is volatile.

## Acceptance mapping

| Contract | SQL / recon evidence |
|---|---|
| ACT-01 | `40_window_coverage.sql`, `60_gold_report.sql`; `ACT-01/*` |
| ACT-02 | `50_user_summaries_prune.sql`, `51_user_summaries_publish.sql`; `ACT-02/*` |
| ACT-03 | `40_window_coverage.sql`, `60_gold_report.sql`; `ACT-03/*` |
| ACT-04 | `33_ddl_gold_latest_view.sql`, `60_gold_report.sql`; `ACT-04/*` |
| ACT-05 | prune/publish/report SQL; `ACT-05/*` |
| ACT-06 | `51_user_summaries_publish.sql`, `60_gold_report.sql`; `ACT-06/*` |

`actions_by_type` map key order is not preserved by Spark; recon compares key/value
pairs as sorted items. Missing user IDs are attributed to `unknown` in gold.
The empty-window path writes an empty report; its average is numeric `0.0` while
the legacy JSON may render `0`. The baseline has no root `stdout.log`.

## Coverage

The fixture recon proves deterministic extraction, the strict `< ds` guard,
missing-day reporting, UTF-8 transport, and offline parity helpers. Target SQL,
Delta MERGE behavior, view resolution, job shape, PAUSED schedule, and rerun
idempotency require the parent's live Databricks window. Invalid UTF-8 and
malformed attribution are exercised by the unit tests.
