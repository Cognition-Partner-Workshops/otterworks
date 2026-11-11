# audit_actor_activity_join

run_token=dbx-d1111 expires=2026-11-24

## Result: RED

The audit tables now exist, but the input contract is still incomplete: Missing ACTION_COUNT in users__user_activity_daily and users__stg_user_activity_daily; USER_AGENT, RAW_LINE and IP_ADDRESS absent from users__login_event and users__stg_login_event. DOCUMENT_COUNT and CLIENT_TYPE are not equivalent. Tagged DESCRIBE checks cover both final and staging alternatives. No incomplete job was run, no target or before-result was created, and no fields were invented.

First failure (preserved): `01f1dd84-1d40-1344-acb9-8789377f93a3` (`TABLE_OR_VIEW_NOT_FOUND`).
The original response and every later input-contract/parity/control/history query are retained in statements.json.
The initial missing-baseline result is historical, not the current reason for a RED row.

## Semantics and input adapter

Both joins remain inner. Null actors map to 0; activity LOGIN_COUNT > 12 maps to 0 and login hour < 8 maps to 0. collect_list order is unspecified; only octet_length is output. Missing ACTION_COUNT is not DOCUMENT_COUNT; USER_AGENT and RAW_LINE cannot be recovered from CLIENT_TYPE. Required unused IP_ADDRESS also has no landing equivalent.

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
make sfx-spark-run JOB=audit_actor_activity_join
curl -s http://localhost:18080/api/v1/applications
# Load genuine original output as audit__spark_audit_actor_activity_join__spark_before in parity schema.
# Only when all required fields are available:
databricks jobs run-now 1091978784638813
# Execute each statement in parity.sql via Statement Execution API, retaining statement_id.
databricks jobs run-now 1091978784638813
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
    "count": 466296,
    "hash": "269021183884531047825102"
  },
  "edge_tests": "passed",
  "fixture_applications": [
    "app-20261111040604-0001"
  ]
}
```

Raw local applications/executors/spills/failures and comparison samples are in
history-evidence.json and fixture-evidence.json. Packaged baseline and current local runs are separate.

## Board row

```json
{
  "source": "etl/spark/jobs/py/audit_actor_activity_join.py",
  "target": "cpw.dbx_d1111_after.audit__spark_audit_actor_activity_join",
  "status": "red",
  "red_reason": "Missing ACTION_COUNT in users__user_activity_daily and users__stg_user_activity_daily; USER_AGENT, RAW_LINE and IP_ADDRESS absent from users__login_event and users__stg_login_event. DOCUMENT_COUNT and CLIENT_TYPE are not equivalent.",
  "first_failure": "[TABLE_OR_VIEW_NOT_FOUND] The table or view `cpw`.`dbx_d1111_before`.`audit__audit_event` cannot be found. Verify the spelling and correctness of the schema and catalog.\nSearch path: [`system`.`session`, `system`.`builtin`, `system`.`ai`, `workspace`.`default`].\nIf you did not qualify the name with a schema, verify the current_schema() output, or qualify the name with the correct schema and catalog.\nTo tolerate the error on drop use DROP VIEW IF EXISTS or DROP TABLE IF EXISTS. SQLSTATE: 42P01; line 2 pos 14",
  "first_failure_statement_id": "01f1dd84-1d40-1344-acb9-8789377f93a3",
  "corrected_parity": "BLOCKED: Missing ACTION_COUNT in users__user_activity_daily and users__stg_user_activity_daily; USER_AGENT, RAW_LINE and IP_ADDRESS absent from users__login_event and users__stg_login_event. DOCUMENT_COUNT and CLIENT_TYPE are not equivalent.",
  "parity_statement_id": null,
  "idempotence": "BLOCKED: no complete live input contract; no job run submitted",
  "idempotence_statement_ids": [],
  "job_id": "1091978784638813",
  "job_run_ids": [],
  "executor_hours": 0.004015278,
  "baseline_app_id": "app-20261110202505-0009",
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
/* run=dbx-d1111 act=spark step=history consumer=audit_actor_activity_join */
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=audit_actor_activity_join */%'
ORDER BY start_time;
```

Ingestion lags 30–40 minutes. The recorded end query is a snapshot, not a claim that newer statements are absent.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-e5a6-1947-9640-a358cca82d80",
    "status": "SUCCEEDED",
    "rows": [
      [
        "01f1dd84-1d40-1344-acb9-8789377f93a3",
        "2026-11-11T03:58:12.143Z",
        "108",
        "0",
        null,
        "FAILED"
      ],
      [
        "01f1dd84-1d6e-15f6-8138-ad5b797b9cd8",
        "2026-11-11T03:58:12.445Z",
        "294",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-333d-106c-a53b-92354c770963",
        "2026-11-11T03:58:49.031Z",
        "400",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-33a1-1a1c-a288-041669ed8aa8",
        "2026-11-11T03:58:49.690Z",
        "235",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-363a-1c23-a0bf-f7a364df8d0d",
        "2026-11-11T03:58:54.050Z",
        "384",
        "0",
        "7",
        "FINISHED"
      ],
      [
        "01f1dd84-36aa-10ab-a721-912b3a2c9745",
        "2026-11-11T03:58:54.778Z",
        "324",
        "0",
        "7",
        "FINISHED"
      ],
      [
        "01f1dd84-d18b-123e-b228-d216d9e0a5f4",
        "2026-11-11T04:03:14.623Z",
        "2243",
        "249",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-d30e-1857-b82f-8febee914633",
        "2026-11-11T04:03:17.160Z",
        "2634",
        "250",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-d4d1-1eee-861a-4037a312bb09",
        "2026-11-11T04:03:20.120Z",
        "2276",
        "251",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-d662-116f-914a-636ddb976db6",
        "2026-11-11T04:03:22.743Z",
        "3043",
        "252",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-d863-1c74-93e3-515fc7594967",
        "2026-11-11T04:03:26.108Z",
        "2140",
        "253",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-d9db-1f16-bf96-9b1f6622011a",
        "2026-11-11T04:03:28.575Z",
        "2120",
        "254",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-db53-16c1-a2f2-d0f7136d88d3",
        "2026-11-11T04:03:31.035Z",
        "2399",
        "255",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-dcf5-1325-9677-6f43ce815833",
        "2026-11-11T04:03:33.773Z",
        "2229",
        "256",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-de82-1e16-9e7d-d8f34c60d1e4",
        "2026-11-11T04:03:36.380Z",
        "2336",
        "2",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-23c3-1860-a76f-f288697cfc20",
        "2026-11-11T04:05:32.564Z",
        "419",
        "1",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-800d-156e-920d-10c3d712a3ff",
        "2026-11-11T04:08:07.399Z",
        "3032",
        "6",
        "6",
        "FINISHED"
      ],
      [
        "01f1dd85-8206-1af6-956c-89afc177ea42",
        "2026-11-11T04:08:10.710Z",
        "2871",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd85-c269-1eb6-86e1-dd1f8c62b69f",
        "2026-11-11T04:09:58.736Z",
        "1820",
        "307",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-c3b3-1b34-9f18-5c3cc50c510b",
        "2026-11-11T04:10:00.898Z",
        "2011",
        "308",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-c525-1516-a17c-d574339628e3",
        "2026-11-11T04:10:03.320Z",
        "3185",
        "4",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-3047-15d5-b267-0a27be6e1c58",
        "2026-11-11T04:13:03.059Z",
        "268",
        "0",
        "9",
        "FINISHED"
      ],
      [
        "01f1dd86-30a0-19be-b574-59fe33a1b922",
        "2026-11-11T04:13:03.643Z",
        "184",
        "0",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-4bfd-134a-b133-3841daa7e940",
        "2026-11-11T04:13:49.551Z",
        "327",
        "0",
        "7",
        "FINISHED"
      ],
      [
        "01f1dd86-4c64-1dac-83cf-b6634f95fb39",
        "2026-11-11T04:13:50.229Z",
        "176",
        "0",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-4cae-1004-a850-dd8361bc26c3",
        "2026-11-11T04:13:50.707Z",
        "344",
        "0",
        "7",
        "FINISHED"
      ],
      [
        "01f1dd86-4d11-18fe-82dd-8cefd882e90a",
        "2026-11-11T04:13:51.360Z",
        "176",
        "0",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-611b-1a9e-b073-aef4999050a0",
        "2026-11-11T04:14:24.982Z",
        "221",
        "0",
        null,
        "FAILED"
      ],
      [
        "01f1dd86-6159-1b6e-adb0-ff19982f4c06",
        "2026-11-11T04:14:25.388Z",
        "167",
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
/* run=dbx-d1111 act=spark step=billing consumer=audit_actor_activity_join */
SELECT usage_metadata.job_id, usage_metadata.job_run_id, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '1091978784638813' AND usage_unit='DBU'
GROUP BY usage_metadata.job_id, usage_metadata.job_run_id;
```

Missing rows are PENDING (billing can lag hours), never zero DBU. Executor-hours come only from
etl/spark/history/baseline.json; executor-hours and DBUs differ, so no savings ratio is computed.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-e7bd-1456-afcc-8db643320e00",
    "status": "SUCCEEDED",
    "rows": []
  }
]
```
