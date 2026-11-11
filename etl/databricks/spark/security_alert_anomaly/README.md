# security_alert_anomaly

run_token=dbx-d1111 expires=2026-11-24

## Result: RED

The audit tables now exist, but the input contract is still incomplete: Missing SCORE and ALERT_TYPE in audit__security_alert and audit__stg_security_alert; categorical SEVERITY_CD is not a numeric anomaly score. Exact local Z_SCORE parity also remains failed. Tagged DESCRIBE checks cover both final and staging alternatives. No incomplete job was run, no target or before-result was created, and no fields were invented.

First failure (preserved): `01f1dd84-1e40-1a8d-9f85-0467d72f7a49` (`TABLE_OR_VIEW_NOT_FOUND`).
The original response and every later input-contract/parity/control/history query are retained in statements.json.
The initial missing-baseline result is historical, not the current reason for a RED row.

## Semantics and input adapter

Python scoring is re-expressed with DataFrame reductions (no RDD API on serverless), population variance max(sum(x*x)/n-mean*mean,0), and stddev fallback 1.0. Null SCORE fails just as float(None) fails. Double reduction order can alter low bits: exact parity must be checked, never silently rounded. SCORE and ALERT_TYPE have no defensible live equivalents; SEVERITY_CD is not numeric SCORE. No scoring data is fabricated.

inputs.sql contains one SELECT per input and only defensible mappings from
warehouse/teradata/ddl/audit/00_tables.sql and users/00_tables.sql
(column aliases are explicit). Comments list unmappable required columns.
Missing columns are intentionally not supplied as NULL/zero/constants. The production
transform fails on incomplete adapters rather than fabricating results.


## Live evidence

Live execution, before-result transfer, corrected comparison and idempotence remain blocked; the default fixture below is not live evidence.

Canonical formatting is Spark STRING for each column in output order, with `<NULL>` for nulls,
pipe-separated; hash = sum(cast(conv(substr(md5(canonical),1,15),16,10) AS DECIMAL(38,0))).
Counts, hashes and up to 20 exact EXCEPT ALL differences each way are checked.
Full replacement writes are idempotent; MERGE metrics do not apply. File counts are not fixed.


## Live evidence

Live execution, before-result transfer, corrected comparison and idempotence remain blocked; the default fixture below is not live evidence.

Canonical formatting is Spark STRING for each column in output order, with `<NULL>` for nulls,
pipe-separated; hash = sum(cast(conv(substr(md5(canonical),1,15),16,10) AS DECIMAL(38,0))).
Counts, hashes and up to 20 exact EXCEPT ALL differences each way are checked.
Full replacement writes are idempotent; MERGE metrics do not apply. File counts are not fixed.

## Serverless standard

- Existing SQL warehouse only; its job.json placeholder is substituted from the secret at registration.
- PySpark environment version 2; no clusters, executor sizing or fixed shuffle counts. No successful PySpark serverless runtime AQE value claimed for blocked jobs; SQL tasks rely on serverless defaults.
- Retries: max_retries=2, min_retry_interval_millis=60000, retry_on_timeout=false, timeout_seconds=1800.
- Delta full replacement; no append duplication, coalesce/repartition, fixed file counts, partitioning or CLUSTER BY.
  No downstream partition-pruning contract requires partitioning. Serverless manages AQE and file sizing.
- Unscheduled jobs and runs use run_token=dbx-d1111, expires=2026-11-24, act=spark tags.
- Tables carry matching COMMENT and run_token/expires/act TBLPROPERTIES; workspace files have header comments.
- audit_daily_summary must finish before lake_compaction_audit; preserve that explicit cross-job order.

## Commands

```sh
docker pull mirror.gcr.io/library/spark:3.5.3-scala2.12-java17-python3-ubuntu
docker pull mirror.gcr.io/library/postgres:16
make sfx-spark-up SFX_SPARK_LANDING="$PWD/etl/spark/.data/landing"
# For LIVE runs: export inputs.sql to headered pipe-separated audit/<TABLE>/20261109.psv
# AFTER fixture generation above; preserve existing fixture inputs/outputs separately.
# Prove exported rows equal live inputs using the canonical count/hash before running.
# Run the unchanged original oracle
make sfx-spark-run JOB=security_alert_anomaly
curl -s http://localhost:18080/api/v1/applications
# Load genuine original output as audit__spark_security_alert_anomaly__spark_before in parity schema.
# Only when all required fields are available:
databricks jobs run-now 859825881744874
# Execute each statement in parity.sql via Statement Execution API, retaining statement_id.
databricks jobs run-now 859825881744874
# Compare the second fingerprint and DESCRIBE HISTORY operationMetrics.
```

Fixture-only migrated harness (never upload those rows as live data): copy the six job directories
to /opt/migrations in spark-master and run spark-submit --master 'local[4]' --py-files
/opt/sfx/spark/.cache/common.zip /opt/migrations/audit_daily_summary/check_fixture.py.
This checks exact output, two local overwrites, thresholds/nulls/case and archive order.

## Local default fixture evidence (not live parity)

```json
{
  "exact_parity": false,
  "idempotent": true,
  "before": {
    "count": 200000,
    "hash": "115319834002649889538599"
  },
  "edge_tests": "passed",
  "fixture_applications": [
    "app-20261111040644-0003"
  ],
  "numeric_diagnostic": {
    "paired_rows": 200000,
    "max_abs_delta": 1.5720758028692217e-13,
    "different_rows": 199859,
    "verdict": "FAIL: exact comparison; no tolerance applied and no correction claimed"
  }
}
```

Raw local applications/executors/spills/failures and comparison samples are in
history-evidence.json and fixture-evidence.json. Packaged baseline and current local runs are separate.

## Board row

```json
{
  "source": "etl/spark/jobs/py/security_alert_anomaly.py",
  "target": "cpw.dbx_d1111_after.audit__spark_security_alert_anomaly",
  "status": "red",
  "red_reason": "Missing SCORE and ALERT_TYPE in audit__security_alert and audit__stg_security_alert; categorical SEVERITY_CD is not a numeric anomaly score. Exact local Z_SCORE parity also remains failed.",
  "first_failure": "[TABLE_OR_VIEW_NOT_FOUND] The table or view `cpw`.`dbx_d1111_before`.`audit__security_alert` cannot be found. Verify the spelling and correctness of the schema and catalog.\nSearch path: [`system`.`session`, `system`.`builtin`, `system`.`ai`, `workspace`.`default`].\nIf you did not qualify the name with a schema, verify the current_schema() output, or qualify the name with the correct schema and catalog.\nTo tolerate the error on drop use DROP VIEW IF EXISTS or DROP TABLE IF EXISTS. SQLSTATE: 42P01; line 2 pos 14",
  "first_failure_statement_id": "01f1dd84-1e40-1a8d-9f85-0467d72f7a49",
  "corrected_parity": "BLOCKED: Missing SCORE and ALERT_TYPE in audit__security_alert and audit__stg_security_alert; categorical SEVERITY_CD is not a numeric anomaly score. Exact local Z_SCORE parity also remains failed.",
  "parity_statement_id": null,
  "idempotence": "BLOCKED: no complete live input contract; no job run submitted",
  "idempotence_statement_ids": [],
  "job_id": "859825881744874",
  "job_run_ids": [],
  "executor_hours": 0.013226667,
  "baseline_app_id": "app-20261110202626-0017",
  "dbu_after": "PENDING: no live job run; never a zero-cost claim",
  "pr": "https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756",
  "local_fixture_exact_parity": false,
  "local_fixture_idempotence": true,
  "additional_blocker": "Exact local Z_SCORE mismatch: distributed floating reduction changed low bits; no rounding, tolerance, or correction accepted",
  "run_token": "dbx-d1111",
  "expires": "2026-11-24"
}
```

## Query history

```sql
/* run=dbx-d1111 act=spark step=history consumer=security_alert_anomaly */
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=security_alert_anomaly */%'
ORDER BY start_time;
```

Ingestion lags 30–40 minutes. The recorded end query is a snapshot, not a claim that newer statements are absent.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-edeb-1ac2-a63e-fb01c031e851",
    "status": "SUCCEEDED",
    "rows": [
      [
        "01f1dd84-1e40-1a8d-9f85-0467d72f7a49",
        "2026-11-11T03:58:13.823Z",
        "95",
        "0",
        null,
        "FAILED"
      ],
      [
        "01f1dd84-1e74-16ca-aef3-acdbc1987c3b",
        "2026-11-11T03:58:14.162Z",
        "328",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-3480-1080-aff1-fb45780d0f0b",
        "2026-11-11T03:58:51.148Z",
        "364",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-34d5-161b-a2f9-05d100ade666",
        "2026-11-11T03:58:51.706Z",
        "314",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-ee88-1334-a4c9-f1814cdeaec1",
        "2026-11-11T04:04:03.257Z",
        "2287",
        "265",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-f013-125e-9df6-093e44f6ed49",
        "2026-11-11T04:04:05.844Z",
        "2162",
        "266",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-f195-1956-9ff7-9c9dd8308281",
        "2026-11-11T04:04:08.377Z",
        "2091",
        "267",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-f315-1653-a8eb-107a60a162a6",
        "2026-11-11T04:04:10.893Z",
        "2770",
        "268",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-f4f1-1f52-a9f0-7e7847d74092",
        "2026-11-11T04:04:14.017Z",
        "2325",
        "269",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-f684-1fa0-864c-69fa85c41a1e",
        "2026-11-11T04:04:16.659Z",
        "2200",
        "270",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-f812-1820-83a2-bab5df9c64cf",
        "2026-11-11T04:04:19.263Z",
        "2320",
        "271",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-f9a4-156c-a957-fc987fdc029f",
        "2026-11-11T04:04:21.896Z",
        "2206",
        "272",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-fb26-16ee-862a-7183128a06e3",
        "2026-11-11T04:04:24.427Z",
        "2153",
        "2",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-24a6-1b8f-a80d-0ed99c030799",
        "2026-11-11T04:05:34.054Z",
        "417",
        "1",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-87ea-1393-b6f4-2cdf07d06f7f",
        "2026-11-11T04:08:20.591Z",
        "3378",
        "4",
        "4",
        "FINISHED"
      ],
      [
        "01f1dd85-8a1f-18ba-98e9-531f89742401",
        "2026-11-11T04:08:24.296Z",
        "3051",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd85-cc0d-1112-9d4d-8e32d9e30c8d",
        "2026-11-11T04:10:14.905Z",
        "2037",
        "311",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-cd76-107f-b9e8-4920fada70f1",
        "2026-11-11T04:10:17.269Z",
        "2031",
        "312",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-cedb-1aec-a593-b2cd8f89eff3",
        "2026-11-11T04:10:19.615Z",
        "2086",
        "313",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-d053-1907-8fbf-74d7a0005962",
        "2026-11-11T04:10:22.077Z",
        "3631",
        "4",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-31ba-1bcb-9559-c47a144d1089",
        "2026-11-11T04:13:05.492Z",
        "372",
        "0",
        "8",
        "FINISHED"
      ],
      [
        "01f1dd86-3223-14b2-8634-b8313fd9a00a",
        "2026-11-11T04:13:06.177Z",
        "453",
        "0",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-4a63-1bf7-8202-7cf08ca99a48",
        "2026-11-11T04:13:46.866Z",
        "342",
        "0",
        "8",
        "FINISHED"
      ],
      [
        "01f1dd86-4ac9-1080-a39e-23b2cd74b0d0",
        "2026-11-11T04:13:47.529Z",
        "388",
        "0",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-6191-1034-b37a-fa1a9cedd1c3",
        "2026-11-11T04:14:25.752Z",
        "168",
        "0",
        null,
        "FAILED"
      ]
    ]
  }
]
```

## Billing

```sql
/* run=dbx-d1111 act=spark step=billing consumer=security_alert_anomaly */
SELECT usage_metadata.job_id, usage_metadata.job_run_id, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '859825881744874' AND usage_unit='DBU'
GROUP BY usage_metadata.job_id, usage_metadata.job_run_id;
```

Missing rows are PENDING (billing can lag hours), never zero DBU. Executor-hours come only from
etl/spark/history/baseline.json; executor-hours and DBUs differ, so no savings ratio is computed.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-efe2-1e73-ae64-e2504c29b158",
    "status": "SUCCEEDED",
    "rows": []
  }
]
```
