# Standard Spark execution

`submit.sh <job>` runs inside the Spark master with its existing environment.
The registry uses JSON-form YAML so the container only needs Python's standard
library. `small` (1 GiB) and `large` (2 GiB) are the only size profiles; both use
one core per executor and at most four executors. AQE coalesces 48 initial
shuffle partitions toward 128 MiB. Standalone dynamic allocation uses shuffle
tracking, not an external shuffle service.

There is one whole-job retry policy: Airflow retries twice with exponential
backoff, starting at one minute and capped at ten minutes. The submit script
never retries. Spark separately retries a failed task up to four attempts.
Legacy registrations stay on cron; changing status to `template` activates the
Airflow DAG. Keep `schedule: null` for a manually triggered DAG.

Migrating a job only changes its registry, code, submit wrapper, cron file and
Kubernetes job directory. Delete the cron file on migration. Snowflake entries
also delete the submit script and application manifest, set `command`, and keep
their per-job kustomization with `resources: []`. Never edit the shared top-level
list during a job migration. Airflow workers need the repository mounted at `/opt/etl`, the
Spark client and network access to the master; set `SFX_SPARK_ROOT` if needed.
Set `SFX_REGISTRY_DIR` to override the registry location. DAG files and the
factory must be deployed together. Secrets are supplied by the worker environment.

## Rerun-safe output

Python `save_partition` and Scala `savePartition` replace exactly one
`run_date=YYYY-MM-DD` parquet partition, retaining other dates. Normal writes
use dynamic partition overwrite; an empty result explicitly empties that date's
partition. Use a stable logical date across retries. Do not mix these helpers
with unpartitioned legacy outputs at the same destination. Partition overwrites
are rerun-safe, not atomic multi-output transactions; serialize writers for the
same destination (the DAGs use `max_active_runs=1`).

`save_jdbc_refresh` / `saveJdbcRefresh` stage a full refresh in PostgreSQL, then
create the target if absent, lock it, delete and insert in one transaction.
Failure rolls back the target; the staging table is removed in `finally`.
Readers see the previous or committed refresh, never a partial load. Empty
frames clear the target. Use schema-qualified identifiers; schema drift fails
rather than silently dropping/recreating the target. These helpers target the
PostgreSQL emulator, not arbitrary JDBC databases. A killed process may leave an
orphan `_sfx_stage_*` table, which can be removed after confirming no active writer.
The original `save()` methods remain unchanged until individual jobs migrate.

## Measurement and screenshots

```
python3 etl/spark/measure.py spark --app <id> > before.json
warehouse/.venv/bin/python etl/spark/measure.py snowflake --job <job> --since <ISO-8601-with-timezone> > after.json
python3 etl/spark/measure.py compare --before before.json --after after.json
python3 etl/spark/screenshot.py --app <id> --output /path/to/evidence
```

Spark measurements download the History Server REST `/logs` archive and use
the exact packaged-baseline event summarizer: executor lifetimes exclude the
driver and end at application completion; failed task attempts contribute spill.
No local event-log path is required. This estate uses zstd-compressed logs.
Snowflake history is bounded to the last seven days and 10,000 queries; hitting
the limit fails rather than silently producing partial totals. Runtime spans
first start to last end; execution time is summed. Compute-hours are the union
of query start/end intervals per warehouse where history reports an execution
size (including compilation/queue time; cache/metadata-only queries excluded),
not billed hours, executor-hours, or credits. Warehouse size is reported, not
silently converted to Spark cores. ACCOUNT_USAGE credits arrive later.
Take `--since` immediately before a run to exclude earlier retries or reruns.

Screenshots need Playwright and its Chromium browser (`python3 -m playwright
install chromium`), or `--executable /path/to/installed/chromium`. Both the Jobs
page and the stage with highest total executor runtime are saved as full-page
PNGs. They are evidence artifacts, not tracked repository files.
