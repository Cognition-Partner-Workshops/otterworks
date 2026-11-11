<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# users_risk_score

| Field | Evidence |
| --- | --- |
| Source | etl/spark/scala/src/main/scala/sfx/UsersRiskScore.scala |
| Target | cpw.dbx_d1111_after.users__spark_users_risk_score (not created) |
| Status | RED |
| First failure | ACTION_COUNT absent from live and staging USER_ACTIVITY_DAILY. Fixture generates DOCUMENT_COUNT and ACTION_COUNT independently; they are not interchangeable. Statement: 01f1dd84-2f0a-1459-9c76-a3402b795f6a |
| Corrected parity | NOT RUN: missing required live input;  |
| Idempotence | NOT RUN |
| Job / runs | 122351353434587 / none |
| Executor-hours before | 0.004293889; packaged History Server app app-20261110202613-0016 |
| DBU after | NOT RUN |
| PR | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2757 |

## Input contract and evidence

`ACTIVITY_ID`, `USER_ID`, `ACTIVITY_DT` and `LOGIN_COUNT` have defensible
aliases, but `ACTION_COUNT` does not exist. `users__stg_user_activity_daily`
also lacks it (200 staging rows; DESCRIBE
`01f1dd84-31a5-1276-9a94-b516be067364`). `DOCUMENT_COUNT` is not a substitute:
`etl/spark/fixture/generate_fixture.py` generates the two metrics independently.
`inputs.sql` deliberately leaves `action_count` unresolved so the deployed job
fails closed before creating a target. No local before result, live job run,
parity result, or idempotence claim was fabricated. The Scala sigmoid is
re-expressed in Python, including primitive-null propagation and Java-exp
overflow behavior; live equivalence remains untested until genuine actions exist.

All submitted Statement Execution IDs are in `evidence.json`; database evidence
is in `cpw.dbx_d1111_parity.results` under `run_label='spark-users_risk_score'` and the
single MERGEd control row `object_name='spark:users_risk_score'`. No other job row is changed.

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
  --json '{"path":"/Workspace/Shared/dbx-d1111-spark/users_risk_score"}'
for file in job.py inputs.sql; do
  python3 - "$file" <<'PY' > /dev/null
import base64, json, os, sys, urllib.request
name = sys.argv[1]
payload = {"path": "/Workspace/Shared/dbx-d1111-spark/users_risk_score/" + name,
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
  "$DATABRICKS_HOST/api/2.1/jobs/run-now" --json '{"job_id":122351353434587}'
```

Do not run this red job until genuine missing source columns have an approved adapter.
Submit each statement in `inputs.sql` / `parity.sql` individually through
`POST /api/2.0/sql/statements`, with `warehouse_id=$DATABRICKS_WAREHOUSE_ID`,
`wait_timeout="50s"`, `format="JSON_ARRAY"`; poll pending IDs using
`GET /api/2.0/sql/statements/<statement_id>`. Keep the leading run comment intact.
The hash uses all output columns in schema order, `<NULL>` for NULL, and native
Spark STRING casts for integers, dates, text and doubles (no rounding or tolerance).

For the legacy baseline, pull both README-specified mirror images, run
`make sfx-spark-up ROWS_PER_TABLE=10 SFX_SPARK_LANDING=<absolute-scratch-dir>`,
then replace generated input PSVs with live adapted exports before
`make sfx-spark-run JOB=users_risk_score SFX_SPARK_LANDING=<absolute-scratch-dir>`.
Never use generated fixture input as live evidence for a red job.
Unit tests: `spark-submit --conf spark.eventLog.enabled=false test_job.py`
from this directory. Syntax/undefined-name lint: `python3 -m flake8 . --select=E9,F63,F7,F82`.

## Query history and billing

```sql
/* run=dbx-d1111 act=spark step=history consumer=users_risk_score */
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=users_risk_score */%'
ORDER BY start_time;
```

The latest history check (01f1dd85-6e8c-17c3-9666-cb7b0318a094) returned
5 rows; selected statement IDs, start times, durations, read/produced rows and
execution statuses are retained in `evidence.json`. Ingestion can lag 30–40
minutes; this is an observed partial snapshot, not proof of absent newer queries.

```sql
/* run=dbx-d1111 act=spark step=billing consumer=users_risk_score */
SELECT usage_metadata.job_id, usage_metadata.job_run_id, usage_unit,
       sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '122351353434587'
  AND usage_date >= DATE '2026-11-11'
GROUP BY ALL;
```

Billing check 01f1dd85-20e8-1497-93b9-f6dcde30b368 returned no rows.
No job runs were submitted for this blocked job; no DBU measurement is claimed.
Executor-hours and DBUs are distinct units; no savings ratio is calculated.
