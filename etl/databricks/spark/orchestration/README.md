# Spark orchestration — dbx-d1111

Run from the repository root with DATABRICKS_HOST, DATABRICKS_TOKEN and
DATABRICKS_WAREHOUSE_ID provided securely in the environment. Python stdlib only.

```sh
python etl/databricks/spark/orchestration/deploy.py deploy
python etl/databricks/spark/orchestration/deploy.py run-now
python etl/databricks/spark/orchestration/deploy.py status 1083346942393644
python etl/databricks/spark/orchestration/collect.py
python etl/databricks/spark/orchestration/board.py
```

Deploy is idempotent: list with pagination, filter exact names client-side,
create if missing, otherwise reset only jobs tagged for this run and act.
run-now refuses a second local trigger and uses a fixed idempotency token.
It supplies no job parameters. Never run the hourly job during verification.

## Standard settings and dependencies

Daily: 01:00 UTC (`0 0 1 * * ?`); hourly: minute 18 UTC
(`0 18 * * * ?`). Both PAUSED, max_concurrent_runs=1. Each task has
max_retries=2, min_retry_interval_millis=60000, retry_on_timeout=false,
timeout_seconds=1800. Tags: run_token=dbx-d1111, expires=2026-11-24, act=spark.
No clusters or infrastructure are created: run_job_task delegates to existing jobs.
The existing jobs retain their serverless AQE, Delta layout and idempotent writes.

Only edges: audit_daily_summary -> lake_compaction_audit;
docs_event_export_hourly -> lake_compaction_documents. These are data dependencies,
not clock offsets. All other 13 daily tasks have no upstream. The existing
lake_compaction_documents internal optimize_export -> compact edge is unchanged.

## Exclusions (existing jobs remain untouched)

Red deployed, unscheduled: billing_usage_append_daily, docs_folder_legacy_report
(also retire candidate; cron commented out), users_active_daily,
audit_actor_activity_join, security_alert_anomaly, compliance_flag_rules,
users_risk_score, doc_version_diff_stats.

Red not deployed: billing_payment_aging, billing_gl_trial_balance,
docs_search_log_parse, users_login_useragent_parse, user_pref_json_flatten,
docs_folder_tree_walk. Kept on common Spark template (`etl/spark/template`):
file_object_binary_extract. Reasons and parity evidence are in BOARD.md and
round-one.json; corrected revenue parity supersedes round-one parity.

## Billing and history

Execute SQL files with `python etl/databricks/spark/orchestration/deploy.py sql <file>`.
Update the control row with `python etl/databricks/spark/orchestration/deploy.py control etl/databricks/spark/orchestration/control.sql`: it DESCRIBEs `migration_control`, runs a prefixed `ALTER TABLE ... ADD COLUMNS` for only the MERGE columns the table lacks (e.g. a fresh `warehouse/databricks/bootstrap.sql` table has no `object_name`), then runs the MERGE. The table is never replaced. `run-now` refuses only when `daily-run.json` records the same daily `job_id` as `deployment.json`.
Substitute a job name and its real job ID. The permitted per-job query is:

```sql
/* run=dbx-d1111 act=spark step=billing consumer=<job> */
SELECT usage_metadata.job_run_id, usage_unit, SUM(usage_quantity) AS quantity
FROM system.billing.usage
WHERE usage_metadata.job_id = '<job_id>'
GROUP BY usage_metadata.job_run_id, usage_unit;
```

Sum by job_run_id, retaining units and statement_id. Include round-one runs,
cross-check reruns and the child job runs in run-evidence.json, not parent task
wrapper runs. No rows means PENDING, never zero. Billing may lag hours.
Query-history template is shown once above the board; counts may lag 30–40 minutes.
Neither billing queries nor history counts were executed in this time-limited
handoff; BOARD deliberately keeps DBUs PENDING rather than inventing results.

Round-one cross-check revenue reruns: 821791725568055, 49614676889700.
Billing sql-task prefix-fix reruns: 984031569498879, 875418758524811
(resolve job ownership with runs/get before including in a per-job total).
