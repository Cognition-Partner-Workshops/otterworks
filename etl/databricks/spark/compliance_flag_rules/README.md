# compliance_flag_rules

run_token=dbx-d1111 expires=2026-11-24

## Result: RED — missing live baseline

First live failure: `01f1dd84-1f73-1d90-b5cf-bf3587046203` (`TABLE_OR_VIEW_NOT_FOUND`).
The tagged SELECT and full response are in statements.json. Tagged SHOW TABLES
checks include `stg_` alternatives in before, after and parity; none exists.
No audit fixture rows, empty substitute targets, or before-results were created in Databricks.
Registered unscheduled serverless job `763368305743207`; **not run** because its
required live inputs do not exist. Two successful runs, live input equality,
before-result import, counts, hashes, EXCEPT ALL and live idempotence are BLOCKED.
Local fixture results below are explicitly not live parity. No corrected live comparison exists.

## Semantics and input adapter

Scala mapPartitions re-expressed in PySpark. Status is case-sensitive: only literal closed is resolved, otherwise severity >= 7000 is review, else monitor. SEVERITY output is INT; IDs LONG. Scala primitive null getters unbox to zero. SEVERITY and USER_ID have no equivalent in audit DDL; no fabricated severity or status lowercasing.

inputs.sql contains one SELECT per input and only defensible mappings from
warehouse/teradata/ddl/audit/01_tables.sql and users/01_tables.sql
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
make sfx-spark-run JOB=compliance_flag_rules
curl -s http://localhost:18080/api/v1/applications
# Only after legitimate live sources, missing-column decisions and prerequisites are resolved:
databricks jobs run-now 763368305743207
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
  "history": {
    "status": "pending local execution"
  },
  "fixture": {
    "status": "pending local execution"
  }
}
```

## Board row

```json
{
  "source": "etl/spark/scala/src/main/scala/sfx/ComplianceFlagRules.scala",
  "target": "cpw.dbx_d1111_after.audit__spark_compliance_flag_rules",
  "status": "red",
  "red_reason": "missing live baseline",
  "first_failure": "[TABLE_OR_VIEW_NOT_FOUND] The table or view `cpw`.`dbx_d1111_before`.`audit__compliance_flag` cannot be found. Verify the spelling and correctness of the schema and catalog.\nSearch path: [`system`.`session`, `system`.`builtin`, `system`.`ai`, `workspace`.`default`].\nIf you did not qualify the name with a schema, verify the current_schema() output, or qualify the name with the correct schema and catalog.\nTo tolerate the error on drop use DROP VIEW IF EXISTS or DROP TABLE IF EXISTS. SQLSTATE: 42P01; line 2 pos 14",
  "first_failure_statement_id": "01f1dd84-1f73-1d90-b5cf-bf3587046203",
  "corrected_parity": "BLOCKED: no live-adapted original result; fixture evidence is not live parity",
  "parity_statement_id": null,
  "idempotence": "BLOCKED: no successful live runs",
  "idempotence_statement_ids": [],
  "job_id": "763368305743207",
  "job_run_ids": [],
  "executor_hours": 0.010249167,
  "baseline_app_id": "app-20261110202929-0029",
  "dbu_after": "PENDING: no live run; no zero-cost claim",
  "pr": ""
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
Ingestion may lag 30–40 minutes; statements.json records the end-of-session result,
not an inference that empty history means no execution.

## Billing

```sql
/* run=dbx-d1111 act=spark step=billing consumer=compliance_flag_rules */
SELECT usage_metadata.job_id, usage_metadata.job_run_id, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '763368305743207'
  AND usage_unit = 'DBU'
GROUP BY usage_metadata.job_id, usage_metadata.job_run_id;
```
Filter by actual job_run_id as well once runs exist. Serverless custom_tags do not
inherit job tags. Missing usage is PENDING, never zero; executor-hours from packaged
History Server baseline and DBUs are different units and no savings ratio is computed.
