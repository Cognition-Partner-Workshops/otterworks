# audit_daily_summary

run_token=dbx-d1111 expires=2026-11-24

## Result: GREEN

The independent live baseline is now available. Original missing-table failure is retained below. Adapted live PSV inputs matched by count/hash, the ORIGINAL Spark job completed locally, and its actual output was loaded to the tagged parity table. Two real serverless job runs passed count/hash and both EXCEPT ALL directions (zero differences). Delta history confirms full replacement and identical output row metrics; this is not a MERGE.

First failure (preserved): `01f1dd84-1cc3-1225-bf2a-84ed7af57330` (`TABLE_OR_VIEW_NOT_FOUND`).
The original response and every later input-contract/parity/control/history query are retained in statements.json.
The initial missing-baseline result is historical, not the current reason for a RED row.

## Semantics and input adapter

Scala aggregate re-expressed in SQL. COUNT(*) retains null-actor events; COUNT(DISTINCT ACTOR_USER_ID) excludes null. This job must succeed before lake_compaction_audit. EVENT_DATE is derived by to_date, not a rolling window.

inputs.sql contains one SELECT per input and only defensible mappings from
warehouse/teradata/ddl/audit/00_tables.sql and users/00_tables.sql
(column aliases are explicit). Comments list unmappable required columns.
Missing columns are intentionally not supplied as NULL/zero/constants. The production
transform fails on incomplete adapters rather than fabricating results.


## Live evidence

Local original History Server application: `app-20261111041452-0006`. Raw executor summaries, spills and failed tasks: live-history-evidence.json. Live input provenance and equality: live-inputs.json. Run IDs, result states, comparison statement IDs and Delta operations: live-result.json.

Canonical formatting is Spark STRING for each column in output order, with `<NULL>` for nulls,
pipe-separated; hash = sum(cast(conv(substr(md5(canonical),1,15),16,10) AS DECIMAL(38,0))).
Counts, hashes and up to 20 exact EXCEPT ALL differences each way are checked.
Full replacement writes are idempotent; MERGE metrics do not apply. File counts are not fixed.


## Live evidence

Local original History Server application: `app-20261111041452-0006`. Raw executor summaries, spills and failed tasks: live-history-evidence.json. Live input provenance and equality: live-inputs.json. Run IDs, result states, comparison statement IDs and Delta operations: live-result.json.

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
make sfx-spark-run JOB=audit_daily_summary
curl -s http://localhost:18080/api/v1/applications
# Load genuine original output as audit__spark_audit_daily_summary__spark_before in parity schema.
# Only when all required fields are available:
databricks jobs run-now 891657763613522
# Execute each statement in parity.sql via Statement Execution API, retaining statement_id.
databricks jobs run-now 891657763613522
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
    "count": 42,
    "hash": "22811971466482165729"
  },
  "edge_tests": "passed",
  "fixture_applications": [
    "app-20261111040536-0000"
  ]
}
```

Raw local applications/executors/spills/failures and comparison samples are in
history-evidence.json and fixture-evidence.json. Packaged baseline and current local runs are separate.

## Board row

```json
{
  "source": "etl/spark/scala/src/main/scala/sfx/AuditDailySummary.scala",
  "target": "cpw.dbx_d1111_after.audit__spark_audit_daily_summary",
  "status": "green",
  "red_reason": "",
  "first_failure": "[TABLE_OR_VIEW_NOT_FOUND] The table or view `cpw`.`dbx_d1111_before`.`audit__audit_event` cannot be found. Verify the spelling and correctness of the schema and catalog.\nSearch path: [`system`.`session`, `system`.`builtin`, `system`.`ai`, `workspace`.`default`].\nIf you did not qualify the name with a schema, verify the current_schema() output, or qualify the name with the correct schema and catalog.\nTo tolerate the error on drop use DROP VIEW IF EXISTS or DROP TABLE IF EXISTS. SQLSTATE: 42P01; line 2 pos 14",
  "first_failure_statement_id": "01f1dd84-1cc3-1225-bf2a-84ed7af57330",
  "corrected_parity": "PASS: input count/hash, output count/hash and EXCEPT ALL both ways",
  "parity_statement_id": "01f1dd86-b135-131a-a11b-b44b581c91d0",
  "idempotence": "PASS: two real serverless runs, identical count/hash; full replacement, not MERGE; numOutputRows identical in both Delta history operations; MERGE metrics not applicable",
  "idempotence_statement_ids": [
    "01f1dd86-b135-131a-a11b-b44b581c91d0",
    "01f1dd86-b709-1dfa-97fe-7db9e6c59adf",
    "01f1dd86-b789-1c70-ae49-5d576e1574b3"
  ],
  "job_id": "891657763613522",
  "job_run_ids": [
    "729010651237413",
    "761924419433112"
  ],
  "executor_hours": 0.015961667,
  "baseline_app_id": "app-20261110202448-0008",
  "dbu_after": "PENDING: billing ingestion can lag hours; not zero DBU",
  "pr": "https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756",
  "local_fixture_exact_parity": true,
  "local_fixture_idempotence": true,
  "live_input": {
    "source_export_statement_id": "01f1dd86-6016-167c-9fd7-ad166a8782e8",
    "source_equality_statement_id": "01f1dd86-60ab-1fde-8860-e539b85ed36b",
    "source_count_hash": [
      "2000",
      "1150761524327518271109"
    ],
    "columns": [
      "AUDIT_EVENT_ID",
      "ACTOR_USER_ID",
      "DOCUMENT_ID",
      "EVENT_TYPE",
      "EVENT_AT",
      "DETAILS"
    ],
    "source_rows": 2000,
    "landing": "audit/AUDIT_EVENT/20261109.psv",
    "local_count_hash": [
      "2000",
      "1150761524327518271109"
    ],
    "equality": "PASS"
  },
  "live_local_app_id": "app-20261111041452-0006",
  "output_count_hash": [
    "24",
    "11889509446007135789"
  ],
  "parity_statement_ids": [
    "01f1dd86-b1d7-1c68-9baf-be690141afe2",
    "01f1dd86-b135-131a-a11b-b44b581c91d0",
    "01f1dd86-b252-1938-b570-f5bed6c6f572",
    "01f1dd86-b2ad-1f0d-a301-dd5c710e8e7e"
  ],
  "job_sql_statement_ids": [],
  "run_token": "dbx-d1111",
  "expires": "2026-11-24"
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

Ingestion lags 30–40 minutes. The recorded end query is a snapshot, not a claim that newer statements are absent.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-e1b5-17c0-9654-ed3a00f7dd95",
    "status": "SUCCEEDED",
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
      ],
      [
        "01f1dd84-c3f6-1fd8-8615-370144270acf",
        "2026-11-11T04:02:51.842Z",
        "1869",
        "241",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-c543-1c81-a1c2-38911a55c38c",
        "2026-11-11T04:02:54.022Z",
        "1773",
        "242",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-c682-1163-9e0d-987a39513645",
        "2026-11-11T04:02:56.108Z",
        "2169",
        "243",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-c806-13d0-8a11-c044530f057e",
        "2026-11-11T04:02:58.653Z",
        "2365",
        "244",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-c9a1-1e2e-9965-906e7d064ac0",
        "2026-11-11T04:03:01.348Z",
        "2237",
        "245",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-cb29-1364-acd3-c3bc436f3d60",
        "2026-11-11T04:03:03.914Z",
        "2315",
        "246",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-ccc7-130a-b67d-1746d65615c4",
        "2026-11-11T04:03:06.626Z",
        "2172",
        "247",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-ce44-1ac3-9a69-f5364d9ab607",
        "2026-11-11T04:03:09.128Z",
        "2234",
        "248",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-cfcc-1f2a-a82b-b6c4a247099e",
        "2026-11-11T04:03:11.700Z",
        "2469",
        "2",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-234e-1dc6-a5c1-a5b858b9aaf5",
        "2026-11-11T04:05:31.800Z",
        "470",
        "1",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-7c20-1459-8540-abdc7827a846",
        "2026-11-11T04:08:00.813Z",
        "3353",
        "6",
        "6",
        "FINISHED"
      ],
      [
        "01f1dd85-7e5d-1c21-8a12-21937792545d",
        "2026-11-11T04:08:04.571Z",
        "2644",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd85-bd85-1c54-86d7-1efb6233c97e",
        "2026-11-11T04:09:50.530Z",
        "2142",
        "305",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-bef9-1970-9dc6-2d4ddd5b99b2",
        "2026-11-11T04:09:52.965Z",
        "2057",
        "306",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-c062-1b83-ba3a-86e67229c055",
        "2026-11-11T04:09:55.332Z",
        "3088",
        "4",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-2cf4-16a7-859d-af11d4e57d5c",
        "2026-11-11T04:12:57.482Z",
        "642",
        "0",
        "24",
        "FINISHED"
      ],
      [
        "01f1dd86-2f70-1853-8f4a-b8bd2ddbee7f",
        "2026-11-11T04:13:01.651Z",
        "321",
        "0",
        "9",
        "FINISHED"
      ],
      [
        "01f1dd86-2fd3-1051-92e7-25f987501df9",
        "2026-11-11T04:13:02.295Z",
        "459",
        "0",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-4d57-177e-b7dc-4167b29d51f9",
        "2026-11-11T04:13:51.819Z",
        "474",
        "2000",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-6016-167c-9fd7-ad166a8782e8",
        "2026-11-11T04:14:23.268Z",
        "618",
        "2000",
        "2000",
        "FINISHED"
      ],
      [
        "01f1dd86-60ab-1fde-8860-e539b85ed36b",
        "2026-11-11T04:14:24.250Z",
        "407",
        "2000",
        "1",
        "FINISHED"
      ]
    ]
  }
]
```

## Billing

```sql
/* run=dbx-d1111 act=spark step=billing consumer=audit_daily_summary */
SELECT usage_metadata.job_id, usage_metadata.job_run_id, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '891657763613522' AND usage_metadata.job_run_id IN ('729010651237413','761924419433112') AND usage_unit='DBU'
GROUP BY usage_metadata.job_id, usage_metadata.job_run_id;
```

Missing rows are PENDING (billing can lag hours), never zero DBU. Executor-hours come only from
etl/spark/history/baseline.json; executor-hours and DBUs differ, so no savings ratio is computed.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-e3e2-10e2-8bc0-c1cc1da9b94b",
    "status": "SUCCEEDED",
    "rows": []
  }
]
```
