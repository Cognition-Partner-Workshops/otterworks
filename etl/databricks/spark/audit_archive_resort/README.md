# audit_archive_resort

run_token=dbx-d1111 expires=2026-11-24

## Result: GREEN

The independent live baseline is now available. Original missing-table failure is retained below. Adapted live PSV inputs matched by count/hash, the ORIGINAL Spark job completed locally, and its actual output was loaded to the tagged parity table. Two real serverless job runs passed count/hash and both EXCEPT ALL directions (zero differences). Delta history confirms full replacement and identical output row metrics; this is not a MERGE. The final archive has zero rows; its equivalent live staging source has 200 rows and no null sort keys. The adapter now reads audit__stg_audit_event_archive. read.sql is the ordered consumption contract: Delta readers must ORDER BY EVENT_TYPE, EVENT_AT, AUDIT_EVENT_ARCHIVE_ID. Initial serverless run 924222549327122 failed because reading spark.sql.adaptive.enabled is unsupported. Two later retry attempts lacked __file__; the adapter path is now the explicit registered workspace path. serverless-failures.json preserves both runtime errors; the diagnostic records UNAVAILABLE instead of claiming true. Two later successful parent runs supply parity/idempotence evidence.

First failure (preserved): `01f1dd84-1ecb-1326-a1f6-6c7eaefcc15a` (`TABLE_OR_VIEW_NOT_FOUND`).
The original response and every later input-contract/parity/control/history query are retained in statements.json.
The initial missing-baseline result is historical, not the current reason for a RED row.

## Semantics and input adapter

RDD sortByKey re-expressed as DataFrame orderBy(EVENT_TYPE, EVENT_AT, AUDIT_EVENT_ARCHIVE_ID), no fixed partition count. Null keys sort first in Spark SQL; original Python tuple sorting with null keys is not verified and must remain RED if encountered. Delta has no intrinsic read ordering: consumers needing order must ORDER BY these keys; physical file count is not a contract.

inputs.sql contains one SELECT per input and only defensible mappings from
warehouse/teradata/ddl/audit/00_tables.sql and users/00_tables.sql
(column aliases are explicit). Comments list unmappable required columns.
Missing columns are intentionally not supplied as NULL/zero/constants. The production
transform fails on incomplete adapters rather than fabricating results.


## Live evidence

Local original History Server application: `app-20261111041534-0008`. Raw executor summaries, spills and failed tasks: live-history-evidence.json. Live input provenance and equality: live-inputs.json. Run IDs, result states, comparison statement IDs and Delta operations: live-result.json.

Canonical formatting is Spark STRING for each column in output order, with `<NULL>` for nulls,
pipe-separated; hash = sum(cast(conv(substr(md5(canonical),1,15),16,10) AS DECIMAL(38,0))).
Counts, hashes and up to 20 exact EXCEPT ALL differences each way are checked.
Full replacement writes are idempotent; MERGE metrics do not apply. File counts are not fixed.


## Live evidence

Local original History Server application: `app-20261111041534-0008`. Raw executor summaries, spills and failed tasks: live-history-evidence.json. Live input provenance and equality: live-inputs.json. Run IDs, result states, comparison statement IDs and Delta operations: live-result.json.

Canonical formatting is Spark STRING for each column in output order, with `<NULL>` for nulls,
pipe-separated; hash = sum(cast(conv(substr(md5(canonical),1,15),16,10) AS DECIMAL(38,0))).
Counts, hashes and up to 20 exact EXCEPT ALL differences each way are checked.
Full replacement writes are idempotent; MERGE metrics do not apply. File counts are not fixed.

## Serverless standard

- Existing SQL warehouse only; its job.json placeholder is substituted from the secret at registration.
- PySpark environment version 2; no clusters, executor sizing or fixed shuffle counts. Runtime AQE value: see serverless-output.json (captured from actual task output).
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
make sfx-spark-run JOB=audit_archive_resort
curl -s http://localhost:18080/api/v1/applications
# Load genuine original output as audit__spark_audit_archive_resort__spark_before in parity schema.
# Only when all required fields are available:
databricks jobs run-now 718985920991406
# Execute each statement in parity.sql via Statement Execution API, retaining statement_id.
databricks jobs run-now 718985920991406
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
    "hash": "115355956684154325017052"
  },
  "edge_tests": "passed",
  "fixture_applications": [
    "app-20261111040710-0004"
  ]
}
```

Raw local applications/executors/spills/failures and comparison samples are in
history-evidence.json and fixture-evidence.json. Packaged baseline and current local runs are separate.

## Board row

```json
{
  "source": "etl/spark/jobs/py/audit_archive_resort.py",
  "target": "cpw.dbx_d1111_after.audit__spark_audit_archive_resort",
  "status": "green",
  "red_reason": "",
  "first_failure": "[TABLE_OR_VIEW_NOT_FOUND] The table or view `cpw`.`dbx_d1111_before`.`audit__audit_event_archive` cannot be found. Verify the spelling and correctness of the schema and catalog.\nSearch path: [`system`.`session`, `system`.`builtin`, `system`.`ai`, `workspace`.`default`].\nIf you did not qualify the name with a schema, verify the current_schema() output, or qualify the name with the correct schema and catalog.\nTo tolerate the error on drop use DROP VIEW IF EXISTS or DROP TABLE IF EXISTS. SQLSTATE: 42P01; line 2 pos 14",
  "first_failure_statement_id": "01f1dd84-1ecb-1326-a1f6-6c7eaefcc15a",
  "corrected_parity": "PASS: input count/hash, output count/hash and EXCEPT ALL both ways",
  "parity_statement_id": "01f1dd87-ac01-1e7f-81e1-08ed15cb2ded",
  "idempotence": "PASS: two real serverless runs, identical count/hash; full replacement, not MERGE; numOutputRows identical in both Delta history operations; MERGE metrics not applicable",
  "idempotence_statement_ids": [
    "01f1dd87-ac01-1e7f-81e1-08ed15cb2ded",
    "01f1dd87-c6a6-1285-993e-9d68c4d18e33",
    "01f1dd87-c73d-1b9f-9377-4667d7b74d4a"
  ],
  "job_id": "718985920991406",
  "job_run_ids": [
    "924222549327122",
    "335490112883267",
    "937972557074798"
  ],
  "executor_hours": 0.003700556,
  "baseline_app_id": "app-20261110202911-0027",
  "dbu_after": "PENDING: billing ingestion can lag hours; not zero DBU",
  "pr": "https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756",
  "local_fixture_exact_parity": true,
  "local_fixture_idempotence": true,
  "live_input": {
    "source_export_statement_id": "01f1dd86-760f-104d-a7e3-85bf822d5c3e",
    "source_equality_statement_id": "01f1dd86-769c-12d1-980f-20164b006f6a",
    "source_count_hash": [
      "200",
      "111302969519797801821"
    ],
    "columns": [
      "AUDIT_EVENT_ARCHIVE_ID",
      "ACTOR_USER_ID",
      "DOCUMENT_ID",
      "EVENT_TYPE",
      "EVENT_AT",
      "DETAILS"
    ],
    "source_rows": 200,
    "landing": "audit/AUDIT_EVENT_ARCHIVE/20261109.psv",
    "local_count_hash": [
      "200",
      "111302969519797801821"
    ],
    "equality": "PASS"
  },
  "live_local_app_id": "app-20261111041534-0008",
  "output_count_hash": [
    "200",
    "111302969519797801821"
  ],
  "parity_statement_ids": [
    "01f1dd87-acc7-160b-9a8c-71f8c5db5ba7",
    "01f1dd87-ac01-1e7f-81e1-08ed15cb2ded",
    "01f1dd87-ad45-1636-81e6-040612c24b64",
    "01f1dd87-adb5-1448-bece-1bb82c13f2fc"
  ],
  "job_sql_statement_ids": [],
  "run_token": "dbx-d1111",
  "expires": "2026-11-24"
}
```

## Query history

```sql
/* run=dbx-d1111 act=spark step=history consumer=audit_archive_resort */
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=audit_archive_resort */%'
ORDER BY start_time;
```

Ingestion lags 30–40 minutes. The recorded end query is a snapshot, not a claim that newer statements are absent.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-f15e-1118-bbcf-35fcb71a0c86",
    "status": "SUCCEEDED",
    "rows": [
      [
        "01f1dd84-1ecb-1326-a1f6-6c7eaefcc15a",
        "2026-11-11T03:58:14.731Z",
        "170",
        "0",
        null,
        "FAILED"
      ],
      [
        "01f1dd84-1f16-1232-ba43-840c8337b1c3",
        "2026-11-11T03:58:15.222Z",
        "374",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-3522-190d-b0ba-165f564a1b2e",
        "2026-11-11T03:58:52.212Z",
        "258",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-3568-1148-b7d1-f4cd03a0b3c3",
        "2026-11-11T03:58:52.669Z",
        "232",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-fca2-185d-998b-8e60fcedeffe",
        "2026-11-11T04:04:26.917Z",
        "2691",
        "273",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-fe72-19e0-8069-7293713c84f1",
        "2026-11-11T04:04:29.958Z",
        "2375",
        "274",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-000d-1f0f-923d-df11f92c4043",
        "2026-11-11T04:04:32.656Z",
        "2635",
        "275",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-01d0-1f06-aaf3-d7c4db1d18ae",
        "2026-11-11T04:04:35.611Z",
        "3031",
        "276",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-03dd-112e-bccf-62cbc256903b",
        "2026-11-11T04:04:39.046Z",
        "2496",
        "277",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-0593-14b9-a148-299d1f985139",
        "2026-11-11T04:04:41.916Z",
        "2316",
        "278",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-071f-1e9f-9ca8-59f839f0c5a7",
        "2026-11-11T04:04:44.516Z",
        "1938",
        "279",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-0876-10dc-83e5-e282c34ee26c",
        "2026-11-11T04:04:46.759Z",
        "2123",
        "280",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-09f4-13cb-9772-86cffdb21d5b",
        "2026-11-11T04:04:49.264Z",
        "2445",
        "2",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-2514-1ed3-b084-b4a22709001d",
        "2026-11-11T04:05:34.777Z",
        "429",
        "1",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-8c25-1d04-a224-48bbd66c6e04",
        "2026-11-11T04:08:27.691Z",
        "3004",
        "4",
        "4",
        "FINISHED"
      ],
      [
        "01f1dd85-8e23-1ac4-b741-4d91739c9ac2",
        "2026-11-11T04:08:31.034Z",
        "2740",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd85-d2b0-1dfa-b2dc-6e8e2ec23cf9",
        "2026-11-11T04:10:26.046Z",
        "2180",
        "314",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-d437-1cd6-85ea-d14c7cd27959",
        "2026-11-11T04:10:28.605Z",
        "2087",
        "315",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-d5ab-1a1e-8c41-b453a10d135e",
        "2026-11-11T04:10:31.043Z",
        "3302",
        "4",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-3298-1366-855d-7a42a2d4c166",
        "2026-11-11T04:13:06.943Z",
        "312",
        "0",
        "8",
        "FINISHED"
      ],
      [
        "01f1dd86-32f4-1da2-b676-861c43533c67",
        "2026-11-11T04:13:07.550Z",
        "392",
        "0",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-4978-15c6-bfcf-b3916d233176",
        "2026-11-11T04:13:45.324Z",
        "468",
        "0",
        "8",
        "FINISHED"
      ],
      [
        "01f1dd86-49f0-115c-a89e-b2f994fcba3e",
        "2026-11-11T04:13:46.107Z",
        "476",
        "0",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-609e-1042-8b7b-a46199e341c2",
        "2026-11-11T04:14:24.157Z",
        "546",
        "200",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-760f-104d-a7e3-85bf822d5c3e",
        "2026-11-11T04:15:00.129Z",
        "567",
        "200",
        "200",
        "FINISHED"
      ],
      [
        "01f1dd86-769c-12d1-980f-20164b006f6a",
        "2026-11-11T04:15:01.054Z",
        "427",
        "200",
        "1",
        "FINISHED"
      ]
    ]
  }
]
```

## Billing

```sql
/* run=dbx-d1111 act=spark step=billing consumer=audit_archive_resort */
SELECT usage_metadata.job_id, usage_metadata.job_run_id, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '718985920991406' AND usage_metadata.job_run_id IN ('924222549327122','335490112883267','937972557074798') AND usage_unit='DBU'
GROUP BY usage_metadata.job_id, usage_metadata.job_run_id;
```

Missing rows are PENDING (billing can lag hours), never zero DBU. Executor-hours come only from
etl/spark/history/baseline.json; executor-hours and DBUs differ, so no savings ratio is computed.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-f346-1a8e-a08e-4ac09757be72",
    "status": "SUCCEEDED",
    "rows": []
  }
]
```
