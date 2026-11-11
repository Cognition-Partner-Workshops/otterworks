# team_graph_components → Databricks serverless

Source: `etl/spark/scala/src/main/scala/sfx/TeamGraphComponents.scala`. Target: `cpw.dbx_d1111_after.users__spark_team_graph_components` via PySpark serverless (`spark_python_task`, environment client 2).

Scala RDD label propagation over the team co-membership graph, re-expressed with DataFrames. Same semantics: edges are ordered pairs of distinct users sharing a team; labels start as the user id; exactly 6 rounds of `min(label)` over the closed neighbourhood (the source's `edges.join(labels) ∪ labels`), so components are not forced to converge. Scala `getAs[Int]` on NULL yields 0; reproduced with `coalesce(...,0)`. The Scala job reads the landing file with `inferSchema` (TEAM_ID/USER_ID inferred `int`).

Inputs (`inputs.sql`): users__team_member → TEAM_MEMBER (team_member_id, team_id, user_id, rtrim(role_cd)). 400 rows; live adapter hash = Spark landing hash (233646412918179117291).

## Board row
| field | value |
| --- | --- |
| source | `etl/spark/scala/src/main/scala/sfx/TeamGraphComponents.scala` |
| target | `cpw.dbx_d1111_after.users__spark_team_graph_components` |
| first failure | Job run 182373249747779 FAILED: `spark.conf.get('spark.sql.adaptive.enabled')` → CONFIG_NOT_AVAILABLE on serverless (no comparison produced); fixed by logging the conf as not readable (`see query history`) |
| corrected parity | 200 = 200 rows, hash 110590925637088257858 both sides, EXCEPT ALL 0/0 — `01f1dd87-0d35-11fa-b87c-4e266ad317de` (diffs `01f1dd87-0de7-1a4c-a49e-a92dbeddb00f`, `01f1dd87-0e3f-1d8f-8951-36bbbd370fc6`) |
| idempotence | run2: 200 rows, same hash, CRTAS numOutputRows 200 → 200 — `01f1dd87-93ab-199b-b3bc-aa79ae62faff`, `01f1dd87-950e-15fa-9334-ab329b5fc703` |
| job_id / run_ids | 296844896049163 / 182373249747779 (failed), 23863445904315, 169354815327145 |
| before (local, live inputs) | app-20261111040140-0000: 12.6 s, 2 executors / 4 cores, 0 failed tasks, 0 spill, 71 stages |
| executor-hours before (History Server baseline) | 0.006136667 (app-20261110202753-0022) |
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
# deploy: import files under /Workspace/Shared/dbx-d1111-spark/team_graph_components/ (workspace/import, format RAW), then
#   jobs/create (or jobs/reset) with job.json
# run: POST /api/2.1/jobs/run-now {"job_id": <id>, "job_parameters": {"step": "run1"}}
# parity: run parity.sql statements on the warehouse (each statement already starts with the run comment)
# local check (inside the spark-master container of `make sfx-spark-up`, landing = live adapted PSVs):
#   LANDING_DIR=/opt/landing LAKE_DIR=/opt/lake PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip:. python3 test_team_graph_components.py
```

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=team_graph_components */%'
ORDER BY start_time;
```

## Billing
```sql
SELECT usage_date, usage_metadata.job_id, usage_metadata.job_run_id, sku_name, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '296844896049163'
GROUP BY ALL ORDER BY usage_date;
```
Rows lag hours; missing rows are PENDING, not zero. Executor-hours (before) and DBUs (after) are different units.
