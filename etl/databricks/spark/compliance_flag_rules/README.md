# compliance_flag_rules

run_token=dbx-d1111 expires=2026-11-24

## Result: RED

The audit tables now exist, but the input contract is still incomplete: Missing SEVERITY and USER_ID in audit__compliance_flag and audit__stg_compliance_flag; FLAG_TYPE is not a numeric severity or user identity. Tagged DESCRIBE checks cover both final and staging alternatives. No incomplete job was run, no target or before-result was created, and no fields were invented.

First failure (preserved): `01f1dd84-1f73-1d90-b5cf-bf3587046203` (`TABLE_OR_VIEW_NOT_FOUND`).
The original response and every later input-contract/parity/control/history query are retained in statements.json.
The initial missing-baseline result is historical, not the current reason for a RED row.

## Semantics and input adapter

Scala mapPartitions re-expressed in PySpark. Status is case-sensitive: only literal closed is resolved, otherwise severity >= 7000 is review, else monitor. SEVERITY output is INT; IDs LONG. Scala primitive null getters unbox to zero. SEVERITY and USER_ID have no equivalent in audit DDL; no fabricated severity or status lowercasing.

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
make sfx-spark-run JOB=compliance_flag_rules
curl -s http://localhost:18080/api/v1/applications
# Load genuine original output as audit__spark_compliance_flag_rules__spark_before in parity schema.
# Only when all required fields are available:
databricks jobs run-now 763368305743207
# Execute each statement in parity.sql via Statement Execution API, retaining statement_id.
databricks jobs run-now 763368305743207
# Compare the second fingerprint and DESCRIBE HISTORY operationMetrics.
```

Fixture-only migrated harness (never upload those rows as live data): copy the six job directories
to /opt/migrations in spark-master and run spark-submit --master 'local[4]' --py-files
/opt/sfx/spark/.cache/common.zip /opt/migrations/audit_daily_summary/check_fixture.py.
This checks exact output, two local overwrites, thresholds/nulls/case and archive order.

## Local default fixture evidence (not live parity)

```json
{
  "exact_parity": true,
  "idempotent": true,
  "before": {
    "count": 200000,
    "hash": "115260492655033151445541"
  },
  "edge_tests": "passed",
  "fixture_applications": [
    "app-20261111040734-0005"
  ]
}
```

Raw local applications/executors/spills/failures and comparison samples are in
history-evidence.json and fixture-evidence.json. Packaged baseline and current local runs are separate.

## Board row

```json
{
  "source": "etl/spark/scala/src/main/scala/sfx/ComplianceFlagRules.scala",
  "target": "cpw.dbx_d1111_after.audit__spark_compliance_flag_rules",
  "status": "red",
  "red_reason": "Missing SEVERITY and USER_ID in audit__compliance_flag and audit__stg_compliance_flag; FLAG_TYPE is not a numeric severity or user identity.",
  "first_failure": "[TABLE_OR_VIEW_NOT_FOUND] The table or view `cpw`.`dbx_d1111_before`.`audit__compliance_flag` cannot be found. Verify the spelling and correctness of the schema and catalog.\nSearch path: [`system`.`session`, `system`.`builtin`, `system`.`ai`, `workspace`.`default`].\nIf you did not qualify the name with a schema, verify the current_schema() output, or qualify the name with the correct schema and catalog.\nTo tolerate the error on drop use DROP VIEW IF EXISTS or DROP TABLE IF EXISTS. SQLSTATE: 42P01; line 2 pos 14",
  "first_failure_statement_id": "01f1dd84-1f73-1d90-b5cf-bf3587046203",
  "corrected_parity": "BLOCKED: Missing SEVERITY and USER_ID in audit__compliance_flag and audit__stg_compliance_flag; FLAG_TYPE is not a numeric severity or user identity.",
  "parity_statement_id": null,
  "idempotence": "BLOCKED: no complete live input contract; no job run submitted",
  "idempotence_statement_ids": [],
  "job_id": "763368305743207",
  "job_run_ids": [],
  "executor_hours": 0.010249167,
  "baseline_app_id": "app-20261110202929-0029",
  "dbu_after": "PENDING: no live job run; never a zero-cost claim",
  "pr": "https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756",
  "local_fixture_exact_parity": true,
  "local_fixture_idempotence": true,
  "run_token": "dbx-d1111",
  "expires": "2026-11-24"
}
```

## Query history

```sql
/* run=dbx-d1111 act=spark step=history consumer=compliance_flag_rules */
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=compliance_flag_rules */%'
ORDER BY start_time;
```

Ingestion lags 30–40 minutes. The recorded end query is a snapshot, not a claim that newer statements are absent.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-f507-1c60-bccc-16c38b75df43",
    "status": "SUCCEEDED",
    "rows": [
      [
        "01f1dd84-1f73-1d90-b5cf-bf3587046203",
        "2026-11-11T03:58:15.835Z",
        "190",
        "0",
        null,
        "FAILED"
      ],
      [
        "01f1dd84-1fc7-1afb-a492-7375438f64b3",
        "2026-11-11T03:58:16.384Z",
        "319",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-35a9-165f-ac01-65694ae7df7d",
        "2026-11-11T03:58:53.095Z",
        "231",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-35ef-1584-8b09-0d11c5588c2e",
        "2026-11-11T03:58:53.553Z",
        "233",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd85-0ba0-186d-b595-a4a0bd0d52fc",
        "2026-11-11T04:04:52.072Z",
        "2289",
        "281",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-0d38-1af5-bb11-ad473b4ca4e0",
        "2026-11-11T04:04:54.745Z",
        "2596",
        "282",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-0ef6-1ab1-91e2-da56f7189845",
        "2026-11-11T04:04:57.672Z",
        "2332",
        "283",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-1088-1055-bcfb-8c0a3504ce66",
        "2026-11-11T04:05:00.298Z",
        "2401",
        "284",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-1229-150b-8c90-c4e8e2fe7f48",
        "2026-11-11T04:05:03.032Z",
        "2412",
        "285",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-13cb-13e8-8744-34bd2f04fcc1",
        "2026-11-11T04:05:05.772Z",
        "2734",
        "286",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-15ac-1340-9727-298882182d4c",
        "2026-11-11T04:05:08.925Z",
        "2196",
        "287",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-1724-1820-9c0c-b40f8b8dab14",
        "2026-11-11T04:05:11.391Z",
        "2211",
        "288",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-18ac-1de3-a1ef-35daa807bae3",
        "2026-11-11T04:05:13.961Z",
        "2222",
        "2",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-2588-147d-9bf5-483e5a3d436e",
        "2026-11-11T04:05:35.533Z",
        "437",
        "1",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-8fdf-10e1-8f79-caf943c91c6a",
        "2026-11-11T04:08:33.940Z",
        "3001",
        "4",
        "4",
        "FINISHED"
      ],
      [
        "01f1dd85-91df-18f3-95f9-455f514454b1",
        "2026-11-11T04:08:37.299Z",
        "2623",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd85-d7d8-13b2-b0d2-1bf441cc1604",
        "2026-11-11T04:10:34.691Z",
        "2020",
        "316",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-d93f-1f1e-ac73-2c34dbfed7ad",
        "2026-11-11T04:10:37.049Z",
        "2030",
        "317",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-daa8-1940-b61c-a893e99be3f2",
        "2026-11-11T04:10:39.413Z",
        "4046",
        "4",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-3362-124f-a663-3ff94568b260",
        "2026-11-11T04:13:08.266Z",
        "328",
        "0",
        "8",
        "FINISHED"
      ],
      [
        "01f1dd86-33c3-1bc2-a055-a635ebd910d9",
        "2026-11-11T04:13:08.906Z",
        "398",
        "0",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-4b33-13a3-a944-4fac359ba195",
        "2026-11-11T04:13:48.224Z",
        "318",
        "0",
        "8",
        "FINISHED"
      ],
      [
        "01f1dd86-4b94-14a5-8471-dd9ca89247be",
        "2026-11-11T04:13:48.862Z",
        "374",
        "0",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-61c9-1429-ac95-0f26f9af6ed7",
        "2026-11-11T04:14:26.119Z",
        "189",
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
/* run=dbx-d1111 act=spark step=billing consumer=compliance_flag_rules */
SELECT usage_metadata.job_id, usage_metadata.job_run_id, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '763368305743207' AND usage_unit='DBU'
GROUP BY usage_metadata.job_id, usage_metadata.job_run_id;
```

Missing rows are PENDING (billing can lag hours), never zero DBU. Executor-hours come only from
etl/spark/history/baseline.json; executor-hours and DBUs differ, so no savings ratio is computed.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-f706-100b-bdc1-0b4090cd804d",
    "status": "SUCCEEDED",
    "rows": []
  }
]
```
