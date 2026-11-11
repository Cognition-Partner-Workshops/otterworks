<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# billing_churn_score

| Field | Evidence |
| --- | --- |
| Source | etl/spark/jobs/py/billing_churn_score.py |
| Target | cpw.dbx_d1111_after.billing__spark_billing_churn_score |
| Status | GREEN |
| First failure | PLAN_ID absent in subscription; first case-sensitive lookup left 100 rows unmapped. Case/padding-aware lookup justified by Teradata NOT CASESPECIFIC DDL. Statement: 01f1dd84-2ed4-1ab0-937d-b9b65246431e |
| Corrected parity | 500 rows; hash 278703278045701988246; EXCEPT ALL empty both directions; 01f1dd84-fe60-1677-8c33-5dd66762bf3a |
| Idempotence | 01f1dd85-26a6-1fd1-b36f-866a62c44413, 01f1dd85-2760-1b56-8278-6c28dac35fe8, 01f1dd85-27bf-1a67-9a12-afed8c7e0c91, 01f1dd84-fffa-1f62-970c-5babf2918b4c, 01f1dd85-281e-1091-b2d7-03e6d03dee01 |
| Job / runs | 843322654414524 / 487564212166246, 1039480886636949, 151365825676628 |
| Executor-hours before | 0.00381; packaged History Server app app-20261110202605-0015 |
| DBU after | PENDING |
| PR | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2757 |

## Input contract and evidence

`SUBSCRIPTION` maps IDs/dates/status directly. `PLAN_ID` is looked up from
`billing__plan_catalog` using `upper(rtrim(PLAN_CODE))` on both sides: the
Teradata DDL declares these code columns NOT CASESPECIFIC and the catalog code
is CHAR(10) (`warehouse/teradata/ddl/billing/00_tables.sql`). The catalog has
40 distinct normalized codes; every one of the 500 subscriptions matches exactly
one plan. The initial case-sensitive lookup left 100 rows unmapped; its output
hash comparison failed (`01f1dd84-ca24-16c3-b775-223287183dfa`), with sampled
EXCEPT ALL results retained beside the corrected comparison in `evidence.json`.
`STATUS` retains exact live case and padding; only Python's literal `"closed"`
gets the score increment, as in the original. No status normalization or guessed
plan suffix parsing is performed.

The ORIGINAL Python job was run with `make sfx-spark-run JOB=billing_churn_score`
on exported live PSV input (500 rows; live and locally Spark-computed hash
`295281877648089008306`). Its parquet was loaded in five 100-row INSERT batches
to `cpw.dbx_d1111_parity.billing__spark_billing_churn_score__spark_before`.
History REST `/api/v1/applications/app-20261111040237-0001` reports 8177 ms,
six executor records, zero failed tasks, and zero memory/disk spill bytes.
The packaged baseline app above, NOT this new run, supplies executor-hours.

The first serverless attempt failed reading the restricted AQE configuration;
the same real run succeeded on its configured retry after making that observation
non-fatal. The subsequent corrected runs both succeeded. Both corrected writes
report `numOutputRows=500`; these are CREATE OR REPLACE writes, not MERGEs, so
MERGE counters are not applicable. Output counts, exact hashes and bidirectional
EXCEPT ALL are unchanged on the second corrected run.

All submitted Statement Execution IDs are in `evidence.json`; database evidence
is in `cpw.dbx_d1111_parity.results` under `run_label='spark-billing_churn_score'` and the
single MERGEd control row `object_name='spark:billing_churn_score'`. No other job row is changed.

## Serverless standard

- Serverless Python task, environment client 2; no cluster or active schedule.
- AQE is serverless-managed. Runtime `spark.sql.adaptive.enabled` reads are
  rejected with `CONFIG_NOT_AVAILABLE` (also reproduced by statement
  `01f1dd84-7b7d-1917-8064-8faaba6470b1`). The runtime logs UNAVAILABLE rather
  than inventing a value; no executor/shuffle/file-count knobs are set.
- Retries: 2; interval: 60000 ms; retry-on-timeout: false; timeout: 1800 seconds.
- Delta CREATE OR REPLACE through DataFrameWriterV2; COMMENT and properties
  carry the run token, expiry and act. No fixed file counts, explicit partition
  or CLUSTER BY: the downstream parquet contract requires none. Platform-managed
  automatic clustering is not disabled.

## Commands

From this directory, with credentials only in environment variables, upload the
two workspace files (create the directory using the workspace mkdirs API first):

```sh
curl --fail -sS -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  "$DATABRICKS_HOST/api/2.0/workspace/mkdirs" \
  --json '{"path":"/Workspace/Shared/dbx-d1111-spark/billing_churn_score"}'
for file in job.py inputs.sql; do
  python3 - "$file" <<'PY' > /dev/null
import base64, json, os, sys, urllib.request
name = sys.argv[1]
payload = {"path": "/Workspace/Shared/dbx-d1111-spark/billing_churn_score/" + name,
           "format": "AUTO", "overwrite": True,
           "content": base64.b64encode(open(name, "rb").read()).decode()}
request = urllib.request.Request(os.environ["DATABRICKS_HOST"].rstrip("/") +
    "/api/2.0/workspace/import", data=json.dumps(payload).encode(),
    headers={"Authorization": "Bearer " + os.environ["DATABRICKS_TOKEN"],
             "Content-Type": "application/json"})
urllib.request.urlopen(request).read()
PY
done
# job.json is the exact settings used with POST /api/2.1/jobs/create.
# Reuse the existing job; do not create duplicates.
curl --fail -sS -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  "$DATABRICKS_HOST/api/2.1/jobs/run-now" --json '{"job_id":843322654414524}'
```

Run the same job again for idempotence; retain both returned run IDs.
Submit each statement in `inputs.sql` / `parity.sql` individually through
`POST /api/2.0/sql/statements`, with `warehouse_id=$DATABRICKS_WAREHOUSE_ID`,
`wait_timeout="50s"`, `format="JSON_ARRAY"`; poll pending IDs using
`GET /api/2.0/sql/statements/<statement_id>`. Keep the leading run comment intact.
The hash uses all output columns in schema order, `<NULL>` for NULL, and native
Spark STRING casts for integers, dates, text and doubles (no rounding or tolerance).

For the legacy baseline, pull both README-specified mirror images, run
`make sfx-spark-up ROWS_PER_TABLE=10 SFX_SPARK_LANDING=<absolute-scratch-dir>`,
then replace generated input PSVs with live adapted exports before
`make sfx-spark-run JOB=billing_churn_score SFX_SPARK_LANDING=<absolute-scratch-dir>`.
Never use generated fixture input as live evidence for a red job.
Unit tests: `spark-submit --conf spark.eventLog.enabled=false test_job.py`
from this directory. Syntax/undefined-name lint: `python3 -m flake8 . --select=E9,F63,F7,F82`.

## Query history and billing

```sql
/* run=dbx-d1111 act=spark step=history consumer=billing_churn_score */
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=billing_churn_score */%'
ORDER BY start_time;
```

The latest history check (01f1dd85-6aa0-1ea8-a210-294c01ff75e3) returned
15 rows. Ingestion is PENDING, not evidence of absent execution; history can lag
30–40 minutes. Re-run the exact query after ingestion catches up.

```sql
/* run=dbx-d1111 act=spark step=billing consumer=billing_churn_score */
SELECT usage_metadata.job_id, usage_metadata.job_run_id, usage_unit,
       sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '843322654414524'
  AND usage_date >= DATE '2026-11-11'
GROUP BY ALL;
```

Billing check 01f1dd85-6ce4-1023-8228-86ce35468c99 returned no rows.
DBU after is PENDING because billing ingestion lags hours, never zero.
Executor-hours and DBUs are distinct units; no savings ratio is calculated.
