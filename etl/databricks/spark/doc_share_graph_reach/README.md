# doc_share_graph_reach → Databricks serverless

Source: `etl/spark/jobs/py/doc_share_graph_reach.py`. Target: `cpw.dbx_d1111_after.documents__spark_doc_share_graph_reach` via PySpark serverless (`spark_python_task`, environment client 2).

Bounded BFS (depth 1..4) from user 1 over owner → shared-with edges, keeping the minimum distance per user. RDD `join`/`subtractByKey` match NULL keys, so joins are null-safe. Live note: the documents user 1 owns are shared only with user 1, so the live output is the seed row (1, 0); the synthetic test in `test_doc_share_graph_reach.py` compares deeper graphs against the original RDD code.

Inputs (`inputs.sql`): documents__doc_share has no owner column. OWNER_USER_ID is looked up from documents__document.owner_user_id on DOCUMENT_ID (UPI of SFX_DOCUMENTS.DOCUMENT, 1000/1000 shares matched, no fan-out); SHARED_WITH_USER_ID ← user_id; PERMISSION ← rtrim(access_level). Live adapter hash = Spark landing hash (577610756767614551315).

## Board row
| field | value |
| --- | --- |
| source | `etl/spark/jobs/py/doc_share_graph_reach.py` |
| target | `cpw.dbx_d1111_after.documents__spark_doc_share_graph_reach` |
| first failure | Direct adapter `owner_user_id` UNRESOLVED_COLUMN on documents__doc_share (`01f1dd84-8402-169a-8691-7c2218c1efdf`) |
| corrected parity | 1 = 1 row, hash 268800694793482522 both sides, EXCEPT ALL 0/0 — `01f1dd87-0fb2-180b-b7d6-b7dbd60c3f99` (owner lookup check `01f1dd84-843c-1eb4-8e97-9c73804d5faa`; first deployed run 662486033745289 also failed on the AQE conf read) |
| idempotence | run2: 1 row, same hash, numOutputRows 1 → 1 — `01f1dd87-9602-1d1e-8470-70d9ce2cd78c`, `01f1dd87-974a-1c59-a054-26612d0930f2` |
| job_id / run_ids | 689940778537169 / 662486033745289 (failed), 801285571668645, 221152053434479 |
| before (local, live inputs) | app-20261111040158-0001: 10.6 s, 2 executors / 2 cores, 0 failed tasks, 0 spill |
| executor-hours before (History Server baseline) | 0.004417778 (app-20261110202808-0023) |
| DBU after | PENDING (see billing query) |
| status | green |

## Standard settings
- Adaptive execution: serverless AQE (default on). Reading `spark.sql.adaptive.enabled` from a serverless job raises `CONFIG_NOT_AVAILABLE`; the job logs that value instead of failing. The source's `--executor-memory/--executor-cores/--total-executor-cores/spark.default.parallelism` and the fixed `HashPartitioner(4)`-style partitioning are removed; no repartition/coalesce.
- Retries: task `max_retries=2`, `min_retry_interval_millis=60000`, `retry_on_timeout=false`, `timeout_seconds=1800`; job `timeout_seconds=3600`, `max_concurrent_runs=1`, no schedule.
- Partition sizing: unpartitioned Delta, no CLUSTER BY (small full-refresh output, no downstream layout contract).
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT` (full refresh, same as the source `mode("overwrite")`).
- Tags: job and runs `run_token=dbx-d1111 expires=2026-11-24 act=spark`; table COMMENT + TBLPROPERTIES carry the same.

## Commands
```sh
# deploy: import files under /Workspace/Shared/dbx-d1111-spark/doc_share_graph_reach/ (workspace/import, format RAW), then
#   jobs/create (or jobs/reset) with job.json
# run: POST /api/2.1/jobs/run-now {"job_id": <id>, "job_parameters": {"step": "run1"}}
# parity: run parity.sql statements on the warehouse (each statement already starts with the run comment)
# local check (inside the spark-master container of `make sfx-spark-up`, landing = live adapted PSVs):
#   LANDING_DIR=/opt/landing LAKE_DIR=/opt/lake PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip:. python3 test_doc_share_graph_reach.py
```

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=doc_share_graph_reach */%'
ORDER BY start_time;
```

## Billing
```sql
SELECT usage_date, usage_metadata.job_id, usage_metadata.job_run_id, sku_name, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '689940778537169'
GROUP BY ALL ORDER BY usage_date;
```
Rows lag hours; missing rows are PENDING, not zero. Executor-hours (before) and DBUs (after) are different units.
