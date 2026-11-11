# docs_folder_tree_walk → Databricks serverless (RED)

Source: `etl/spark/jobs/py/docs_folder_tree_walk.py`. Intended target: `cpw.dbx_d1111_after.documents__spark_docs_folder_tree_walk` via PySpark serverless (`spark_python_task`). Not deployed.

The job walks `FOLDER.PARENT_FOLDER_ID` 20 times to find each folder's root and depth. The live baseline has no parent pointer:
`documents__folder` and `documents__stg_folder` carry folder_id, owner_user_id, customer_id, folder_name, created_dt only
(same as `warehouse/teradata/ddl/documents/00_tables.sql`), and no column in `cpw.dbx_d1111_before` matches `%parent%`.
Mapping PARENT_FOLDER_ID would mean inventing the hierarchy, so the row is red.

`docs_folder_tree_walk.py` keeps the re-expression ready (same quirks: `lookup.get(cur) or cur` does not move on a parent of 0 but still counts depth; cycles keep counting for 20 steps). `test_docs_folder_tree_walk.py` checks it against the original job output on the generated fixture and against the original RDD code on edge cases. `job.json` is the settings it would use.

## Board row
| field | value |
| --- | --- |
| source | `etl/spark/jobs/py/docs_folder_tree_walk.py` |
| target | `cpw.dbx_d1111_after.documents__spark_docs_folder_tree_walk` (not created) |
| first failure | `inputs.sql` → UNRESOLVED_COLUMN `parent_folder_id` (`01f1dd84-82aa-1550-a0c6-e5bb66c01aba`) |
| checked | folder/stg_folder columns `01f1dd84-82e9-1e9d-8534-02855f14ab40`; `%parent%` columns in before schema = 0 `01f1dd84-836f-1d33-a414-b0e0135002b8` |
| corrected parity | none (no live equivalent) |
| idempotence | not run |
| job_id / run_ids | none |
| executor-hours before (History Server baseline) | 0.008423056 (app-20261110202742-0021) |
| DBU after | n/a |
| status | red: live baseline has no PARENT_FOLDER_ID (documents__folder, documents__stg_folder) |

## Standard settings (as prepared)
Serverless AQE; source `--executor-memory 1g --executor-cores 1 --num-executors 2 spark.default.parallelism=4` removed; task retries 2 / 60000 ms / no retry on timeout / 1800 s; `CREATE OR REPLACE TABLE AS SELECT`; unpartitioned Delta.

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=docs_folder_tree_walk */%'
ORDER BY start_time;
```
