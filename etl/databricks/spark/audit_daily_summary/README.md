# audit_daily_summary

run_token=dbx-d1111 expires=2026-11-24

## Result: RED — missing live baseline

First live failure: `01f1dd84-1cc3-1225-bf2a-84ed7af57330` (`TABLE_OR_VIEW_NOT_FOUND`).
The tagged SELECT and full response are in statements.json. Tagged SHOW TABLES
checks include `stg_` alternatives in before, after and parity; none exists.
No audit fixture rows, empty substitute targets, or before-results were created in Databricks.
Registered unscheduled serverless job `891657763613522`; **not run** because its
required live inputs do not exist. Two successful runs, live input equality,
before-result import, counts, hashes, EXCEPT ALL and live idempotence are BLOCKED.
Local fixture results below are explicitly not live parity. No corrected live comparison exists.

## Semantics and input adapter

Scala aggregate re-expressed in SQL. COUNT(*) retains null-actor events; COUNT(DISTINCT ACTOR_USER_ID) excludes null. This job must succeed before lake_compaction_audit. EVENT_DATE is derived by to_date, not a rolling window.

inputs.sql contains one SELECT per input and only defensible mappings from
warehouse/teradata/ddl/audit/00_tables.sql and users/00_tables.sql
(column aliases are explicit). Comments list unmappable required columns.
Missing columns are intentionally not supplied as NULL/zero/constants. The production
transform fails on incomplete adapters rather than fabricating results.

## Serverless standard

- SQL tasks use the existing warehouse (job.json placeholder is resolved in memory at registration).
  PySpark tasks use environment version 2; no cluster or executor sizing.
- Serverless AQE defaults apply; PySpark prints spark.sql.adaptive.enabled at runtime.
  No successful serverless runtime value is claimed while blocked.
- max_retries=2, min_retry_interval_millis=60000, retry_on_timeout=false, timeout_seconds=1800.
- Delta full replacement is idempotent, not append. No manual repartition/coalesce,
  shuffle partition count, fixed file count, partitioning or CLUSTER BY: no downstream
  partition-pruning contract requires it. Delta/serverless chooses file sizing.
- No schedule; tags run_token=dbx-d1111, expires=2026-11-24, act=spark propagate to runs.
- Targets carry COMMENT and run_token/expires/act table properties.

## Commands

```sh
# Local default fixture only; never upload it as live audit data.
docker pull mirror.gcr.io/library/spark:3.5.3-scala2.12-java17-python3-ubuntu
docker pull mirror.gcr.io/library/postgres:16
make sfx-spark-up SFX_SPARK_LANDING="$PWD/etl/spark/.data/landing"
# Run original oracle unchanged
make sfx-spark-run JOB=audit_daily_summary
curl -s http://localhost:18080/api/v1/applications
# Only after legitimate live sources, missing-column decisions and prerequisites are resolved:
databricks jobs run-now 891657763613522
# Run parity.sql with Statement Execution API and record each statement_id;
# run-now a second time, then compare its idempotence fingerprint/history metrics.
```

Local migrated comparison harness: audit_daily_summary/check_fixture.py. Copy the six
job directories to a writable /opt/migrations inside spark-master, then run:
```sh
/opt/spark/bin/spark-submit --master 'local[4]' --py-files /opt/sfx/spark/.cache/common.zip /opt/migrations/audit_daily_summary/check_fixture.py
```
It uses the same PSV landing and original output, writes two separate local migrated
outputs, computes count + canonical string MD5 sum and exact EXCEPT ALL samples both ways,
and checks edge cases. No local fixture is represented as an adapted live input.

## Local evidence

```json
{
  "fixture_exact_parity": true,
  "fixture_idempotence": true,
  "edge_tests": "passed",
  "aqe_local": "true",
  "fixture_before": {
    "count": 42,
    "hash": "22811971466482165729"
  },
  "fixture_run1": {
    "count": 42,
    "hash": "22811971466482165729"
  },
  "fixture_run2": {
    "count": 42,
    "hash": "22811971466482165729"
  },
  "local_apps": [
    {
      "app_id": "app-20261111040536-0000",
      "duration_ms": 19785,
      "failed_tasks": 0,
      "memory_bytes_spilled": 0,
      "disk_bytes_spilled": 0
    }
  ]
}
```
Raw local applications, executor summaries, spill/failure totals and task duration
quantiles are in history-evidence.json; exact comparison samples are in fixture-evidence.json.
Packaged baseline metrics and current local reruns are separate: a rerun need not
reproduce a packaged failure or exactly the same spill volume.

## Board row

```json
{
  "source": "etl/spark/scala/src/main/scala/sfx/AuditDailySummary.scala",
  "target": "cpw.dbx_d1111_after.audit__spark_audit_daily_summary",
  "status": "red",
  "red_reason": "missing live baseline",
  "first_failure": "[TABLE_OR_VIEW_NOT_FOUND] The table or view `cpw`.`dbx_d1111_before`.`audit__audit_event` cannot be found. Verify the spelling and correctness of the schema and catalog.\nSearch path: [`system`.`session`, `system`.`builtin`, `system`.`ai`, `workspace`.`default`].\nIf you did not qualify the name with a schema, verify the current_schema() output, or qualify the name with the correct schema and catalog.\nTo tolerate the error on drop use DROP VIEW IF EXISTS or DROP TABLE IF EXISTS. SQLSTATE: 42P01; line 2 pos 14",
  "first_failure_statement_id": "01f1dd84-1cc3-1225-bf2a-84ed7af57330",
  "corrected_parity": "BLOCKED: no live-adapted original result; fixture evidence is not live parity",
  "parity_statement_id": null,
  "idempotence": "BLOCKED: no successful live runs",
  "idempotence_statement_ids": [],
  "job_id": "891657763613522",
  "job_run_ids": [],
  "executor_hours": 0.015961667,
  "baseline_app_id": "app-20261110202448-0008",
  "dbu_after": "PENDING: no live run; no zero-cost claim",
  "pr": "https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756",
  "local_fixture_exact_parity": true,
  "local_fixture_idempotence": true
}
```

## Query history

```sql
/* run=dbx-d1111 act=spark step=history consumer=audit_daily_summary */
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=audit_daily_summary */%'
ORDER BY start_time;
```
Ingestion may lag 30–40 minutes; statements.json records the end-of-session result,
not an inference that empty history means no execution.
Latest query result(s):
```json
[
  {
    "statement_id": "01f1dd85-7c20-1459-8540-abdc7827a846",
    "state": "SUCCEEDED",
    "rows": [
      [
        "01f1dd84-1cc3-1225-bf2a-84ed7af57330",
        "2026-11-11T03:58:11.321Z",
        "142",
        "0",
        null,
        "FAILED"
      ],
      [
        "01f1dd84-1cfd-1209-9dcc-ada0ac31906d",
        "2026-11-11T03:58:11.702Z",
        "232",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-201e-1d86-a9b2-a7e373b8678f",
        "2026-11-11T03:58:16.956Z",
        "338",
        "0",
        "32",
        "FINISHED"
      ],
      [
        "01f1dd84-208c-1570-a734-4c10790f20f9",
        "2026-11-11T03:58:17.672Z",
        "334",
        "0",
        "9",
        "FINISHED"
      ],
      [
        "01f1dd84-32c1-1db9-bdca-bff7ae453b85",
        "2026-11-11T03:58:48.223Z",
        "231",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-3301-10b8-95e4-5b690988be18",
        "2026-11-11T03:58:48.636Z",
        "218",
        "0",
        "0",
        "FINISHED"
      ]
    ]
  }
]
```
Empty results before that lag window are PENDING ingestion, not missing evidence.

## Billing

```sql
/* run=dbx-d1111 act=spark step=billing consumer=audit_daily_summary */
SELECT usage_metadata.job_id, usage_metadata.job_run_id, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '891657763613522'
  AND usage_unit = 'DBU'
GROUP BY usage_metadata.job_id, usage_metadata.job_run_id;
```
Filter by actual job_run_id as well once runs exist. Serverless custom_tags do not
inherit job tags. Missing usage is PENDING, never zero; executor-hours from packaged
History Server baseline and DBUs are different units and no savings ratio is computed.
Latest billing result(s):
```json
[
  {
    "statement_id": "01f1dd85-7e5d-1c21-8a12-21937792545d",
    "state": "SUCCEEDED",
    "rows": []
  }
]
```
