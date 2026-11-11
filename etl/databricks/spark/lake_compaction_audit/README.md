# lake_compaction_audit

run_token=dbx-d1111 expires=2026-11-24

## Result: GREEN

The independent live baseline is now available. Original missing-table failure is retained below. Adapted live PSV inputs matched by count/hash, the ORIGINAL Spark job completed locally, and its actual output was loaded to the tagged parity table. Two real serverless job runs passed count/hash and both EXCEPT ALL directions (zero differences). Delta history confirms full replacement and identical output row metrics; this is not a MERGE.

First failure (preserved): `01f1dd84-1dc1-1edd-a61b-c08fc01c5233` (`TABLE_OR_VIEW_NOT_FOUND`).
The original response and every later input-contract/parity/control/history query are retained in statements.json.
The initial missing-baseline result is historical, not the current reason for a RED row.

## Semantics and input adapter

Depends on the OUTPUT of audit_daily_summary, not the legacy AUDIT_DAILY_SUMMARY landing table. Order: run audit_daily_summary successfully, then this job. INSERT/CTAS copies its four output columns; coalesce(2) is intentionally removed. Job has no active schedule; combined cross-job orchestration must enforce this dependency.

inputs.sql contains one SELECT per input and only defensible mappings from
warehouse/teradata/ddl/audit/00_tables.sql and users/00_tables.sql
(column aliases are explicit). Comments list unmappable required columns.
Missing columns are intentionally not supplied as NULL/zero/constants. The production
transform fails on incomplete adapters rather than fabricating results.


## Live evidence

Local original History Server application: `app-20261111041519-0007`. Raw executor summaries, spills and failed tasks: live-history-evidence.json. Live input provenance and equality: live-inputs.json. Run IDs, result states, comparison statement IDs and Delta operations: live-result.json.

Canonical formatting is Spark STRING for each column in output order, with `<NULL>` for nulls,
pipe-separated; hash = sum(cast(conv(substr(md5(canonical),1,15),16,10) AS DECIMAL(38,0))).
Counts, hashes and up to 20 exact EXCEPT ALL differences each way are checked.
Full replacement writes are idempotent; MERGE metrics do not apply. File counts are not fixed.


## Live evidence

Local original History Server application: `app-20261111041519-0007`. Raw executor summaries, spills and failed tasks: live-history-evidence.json. Live input provenance and equality: live-inputs.json. Run IDs, result states, comparison statement IDs and Delta operations: live-result.json.

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
make sfx-spark-run JOB=audit_daily_summary
make sfx-spark-run JOB=lake_compaction_audit
curl -s http://localhost:18080/api/v1/applications
# Load genuine original output as audit__spark_lake_compaction_audit__spark_before in parity schema.
# Only when all required fields are available:
databricks jobs run-now 495078759320783
# Execute each statement in parity.sql via Statement Execution API, retaining statement_id.
databricks jobs run-now 495078759320783
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
    "app-20261111040628-0002"
  ]
}
```

Raw local applications/executors/spills/failures and comparison samples are in
history-evidence.json and fixture-evidence.json. Packaged baseline and current local runs are separate.

## Board row

```json
{
  "source": "etl/spark/jobs/py/lake_compaction_audit.py",
  "target": "cpw.dbx_d1111_after.audit__spark_lake_compaction_audit",
  "status": "green",
  "red_reason": "",
  "first_failure": "[TABLE_OR_VIEW_NOT_FOUND] The table or view `cpw`.`dbx_d1111_before`.`audit__audit_daily_summary` cannot be found. Verify the spelling and correctness of the schema and catalog.\nSearch path: [`system`.`session`, `system`.`builtin`, `system`.`ai`, `workspace`.`default`].\nIf you did not qualify the name with a schema, verify the current_schema() output, or qualify the name with the correct schema and catalog.\nTo tolerate the error on drop use DROP VIEW IF EXISTS or DROP TABLE IF EXISTS. SQLSTATE: 42P01; line 2 pos 14",
  "first_failure_statement_id": "01f1dd84-1dc1-1edd-a61b-c08fc01c5233",
  "corrected_parity": "PASS: input count/hash, output count/hash and EXCEPT ALL both ways",
  "parity_statement_id": "01f1dd86-be62-183f-9a53-a7b13ee70d83",
  "idempotence": "PASS: two real serverless runs, identical count/hash; full replacement, not MERGE; numOutputRows identical in both Delta history operations; MERGE metrics not applicable",
  "idempotence_statement_ids": [
    "01f1dd86-be62-183f-9a53-a7b13ee70d83",
    "01f1dd86-c443-1a29-a4cb-579ed75fd474",
    "01f1dd86-c4c7-171c-9c87-2d0241eea15b"
  ],
  "job_id": "495078759320783",
  "job_run_ids": [
    "522129685846599",
    "566170884712306"
  ],
  "executor_hours": 0.001205833,
  "baseline_app_id": "app-20261110202735-0020",
  "dbu_after": "PENDING: billing ingestion can lag hours; not zero DBU",
  "pr": "https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756",
  "local_fixture_exact_parity": true,
  "local_fixture_idempotence": true,
  "live_input": {
    "source_equality_statement_id": "01f1dd86-b880-1559-8506-381eaa91a521",
    "source": "cpw.dbx_d1111_after.audit__spark_audit_daily_summary",
    "source_count_hash": [
      "24",
      "11889509446007135789"
    ],
    "local_count_hash": [
      "24",
      "11889509446007135789"
    ],
    "equality": "PASS"
  },
  "live_local_app_id": "app-20261111041519-0007",
  "output_count_hash": [
    "24",
    "11889509446007135789"
  ],
  "parity_statement_ids": [
    "01f1dd86-bf02-1102-a687-344fc3ff7c0a",
    "01f1dd86-be62-183f-9a53-a7b13ee70d83",
    "01f1dd86-bf80-1c7f-8a99-ec8762bc0ad8",
    "01f1dd86-bfe1-1bd8-a1e6-b542bcea8664"
  ],
  "job_sql_statement_ids": [],
  "run_token": "dbx-d1111",
  "expires": "2026-11-24"
}
```

## Query history

```sql
/* run=dbx-d1111 act=spark step=history consumer=lake_compaction_audit */
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=lake_compaction_audit */%'
ORDER BY start_time;
```

Ingestion lags 30–40 minutes. The recorded end query is a snapshot, not a claim that newer statements are absent.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-e96c-1f31-8f37-8b57b040fff6",
    "status": "SUCCEEDED",
    "rows": [
      [
        "01f1dd84-1dc1-1edd-a61b-c08fc01c5233",
        "2026-11-11T03:58:12.991Z",
        "108",
        "0",
        null,
        "FAILED"
      ],
      [
        "01f1dd84-1df7-179e-825a-43cec72fa232",
        "2026-11-11T03:58:13.342Z",
        "271",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-33e4-181e-af2f-d1e3d1c3d53d",
        "2026-11-11T03:58:50.130Z",
        "244",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-3427-1b5a-a251-ec3d5ee76a64",
        "2026-11-11T03:58:50.569Z",
        "387",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd84-e01c-1ff4-9b55-889ba0e6c2d5",
        "2026-11-11T04:03:39.067Z",
        "2518",
        "257",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-e1ce-1bf3-993f-01fbe3c69a4f",
        "2026-11-11T04:03:41.910Z",
        "2173",
        "258",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-e34b-1fba-ba04-281ac74aea5b",
        "2026-11-11T04:03:44.406Z",
        "2023",
        "259",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-e4b4-153c-ba5a-e0310b869fee",
        "2026-11-11T04:03:46.768Z",
        "2088",
        "260",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-e626-196a-a70b-bd6c578686ae",
        "2026-11-11T04:03:49.196Z",
        "3211",
        "431",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-e842-17f2-8d95-a00d49598a6c",
        "2026-11-11T04:03:52.733Z",
        "2336",
        "262",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-e9d8-190a-8822-586b30739905",
        "2026-11-11T04:03:55.395Z",
        "2239",
        "263",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-eb5f-1a6d-9e89-978f258cda76",
        "2026-11-11T04:03:57.957Z",
        "2245",
        "264",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-ece8-1720-a833-8b39892c0c66",
        "2026-11-11T04:04:00.533Z",
        "2391",
        "2",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd84-f44f-132c-89c4-eb40c28b47cd",
        "2026-11-11T04:04:12.950Z",
        "236",
        "0",
        null,
        "FAILED"
      ],
      [
        "01f1dd85-2433-1d4e-b7c7-cefe6a18aea9",
        "2026-11-11T04:05:33.301Z",
        "451",
        "1",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-83d9-1665-94c3-5cbd0ef84102",
        "2026-11-11T04:08:13.768Z",
        "3190",
        "4",
        "4",
        "FINISHED"
      ],
      [
        "01f1dd85-85ee-166a-a0cc-0ec3f7c27b13",
        "2026-11-11T04:08:17.262Z",
        "3152",
        "0",
        "0",
        "FINISHED"
      ],
      [
        "01f1dd85-c742-145e-abba-362c02c0140c",
        "2026-11-11T04:10:06.864Z",
        "1943",
        "309",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-c899-1431-89fe-b12be59ca14e",
        "2026-11-11T04:10:09.112Z",
        "1914",
        "310",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd85-c9f0-1e27-ae59-387c211f676c",
        "2026-11-11T04:10:11.366Z",
        "3185",
        "4",
        "1",
        "FINISHED"
      ],
      [
        "01f1dd86-30ec-1307-930c-88d6164cf67f",
        "2026-11-11T04:13:04.138Z",
        "348",
        "0",
        "7",
        "FINISHED"
      ],
      [
        "01f1dd86-3152-16cd-9735-bd484e5554ab",
        "2026-11-11T04:13:04.811Z",
        "385",
        "0",
        "1",
        "FINISHED"
      ]
    ]
  }
]
```

## Billing

```sql
/* run=dbx-d1111 act=spark step=billing consumer=lake_compaction_audit */
SELECT usage_metadata.job_id, usage_metadata.job_run_id, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '495078759320783' AND usage_metadata.job_run_id IN ('522129685846599','566170884712306') AND usage_unit='DBU'
GROUP BY usage_metadata.job_id, usage_metadata.job_run_id;
```

Missing rows are PENDING (billing can lag hours), never zero DBU. Executor-hours come only from
etl/spark/history/baseline.json; executor-hours and DBUs differ, so no savings ratio is computed.
Latest result:
```json
[
  {
    "statement_id": "01f1dd87-ebf0-1822-bb1c-60f080c4172e",
    "status": "SUCCEEDED",
    "rows": []
  }
]
```
