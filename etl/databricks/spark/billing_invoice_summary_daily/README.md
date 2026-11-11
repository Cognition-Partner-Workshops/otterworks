<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# billing_invoice_summary_daily -> Databricks SQL (serverless)

Source `etl/spark/jobs/py/billing_invoice_summary_daily.py` -> target `cpw.dbx_d1111_after.billing__spark_billing_invoice_summary_daily`. Status **green**.

Files: `inputs.sql` (live -> landing adapter, one SELECT per landing table), `job.sql` (migrated logic, `sql_task` file on the serverless warehouse), `job.json` (Jobs API 2.1 settings), `parity.sql`.

## Run
```sh
# upload + create (no schedule) + run twice; WAREHOUSE_ID is substituted into job.json at create time
databricks workspace import /Workspace/Shared/dbx-d1111-spark/billing_invoice_summary_daily/job.sql --file job.sql --format AUTO --overwrite
databricks jobs create --json @job.json          # job_id 822926870681999
databricks jobs run-now 822926870681999             # run1 960961565316335
databricks jobs run-now 822926870681999             # run2 672280075759296
```

## Parity
1. Export each `inputs.sql` SELECT to `billing/<TABLE>/<yyyymmdd>.psv`, `make sfx-spark-up SFX_SPARK_LANDING=<dir>`, `make sfx-spark-run JOB=billing_invoice_summary_daily SFX_SPARK_LANDING=<dir>`; History Server: `curl localhost:18080/api/v1/applications/<app>`.
2. Load `etl/spark/.data/lake/billing/billing_invoice_summary_daily` into `cpw.dbx_d1111_parity.billing__spark_billing_invoice_summary_daily__spark_before`.
3. Run each statement of `parity.sql` (count + order-independent hash, EXCEPT ALL both ways); after run2 re-run the count-hash statement with `step=idempotence`.

Inputs: INVOICE_HDR 2100 rows hash 01f1dd84-a50d-1490-a341-31f521132ea2; INVOICE_LINE 4434 rows hash 01f1dd84-a5ce-1012-8028-54b959442b82; equal to Spark-side counts/hashes.
Local Spark run (History Server): app-20261111040235-0000 (10671 ms, 3 executors, 0 failed tasks, 0 spill).

Crosscheck: job.sql now starts with the `/* run=dbx-d1111 act=spark ... */` prefix (the leading `-- run_token` comment had made system.query.history statement_text miss the prefix). Same SQL otherwise; run3 984031569498879, 01f1dd8b-9812-125b-a5bf-45ffdf39ceed: 692 rows, hash 396927275775047228202 unchanged.

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=billing_invoice_summary_daily */%' ORDER BY start_time
```
Billing: `SELECT * FROM system.billing.usage WHERE usage_metadata.job_id = '822926870681999'` (lags hours; report PENDING, never zero).

## Standard settings
- Adaptive execution: serverless SQL warehouse (AQE on by default); no executor memory/cores, shuffle partitions, repartition/coalesce.
- Retries: task `max_retries=2`, `min_retry_interval_millis=60000`, `retry_on_timeout=false`, `timeout_seconds=1800`; no schedule.
- Partition sizing: Delta target, no fixed file count, no CLUSTER BY/partitioning (no downstream contract needs it).
- Idempotent writes: CREATE OR REPLACE TABLE ... AS (Spark mode=overwrite).
- Tags `run_token=dbx-d1111`, `expires=2026-11-24`, `act=spark` on job; table COMMENT + TBLPROPERTIES.

## Board row
| job | source | target | first failure (statement_id) | corrected parity (statement_id) | idempotence (statement_ids) | job_id / run_ids | executor-hours before (baseline app) | DBU after | status |
|---|---|---|---|---|---|---|---|---|---|
| `billing_invoice_summary_daily` | `etl/spark/jobs/py/billing_invoice_summary_daily.py` | `cpw.dbx_d1111_after.billing__spark_billing_invoice_summary_daily` | inputs.sql INVOICE_LINE adapter failed to parse (comment ended the statement); fixed and re-run. DUE_DATE/STATUS unmapped but not read by the job (`01f1dd84-95f3-1cda-a35c-ca54dfaa0b3f`) | 692 = 692 rows, hash 396927275775047228202 both sides, EXCEPT ALL 0/0 (`01f1dd85-0f4b-11a7-a17a-49b3b10b6087`) | run2: 692 rows, same hash; CREATE OR REPLACE numOutputRows 692 both versions (`01f1dd85-29df-115d-81b3-1f9173126620`, `01f1dd85-2e59-11e2-99ca-b7af5b74dc61`) | 822926870681999 / 960961565316335, 672280075759296 | 0.005417778 (app-20261110202324-0000) | PENDING | **green** |

