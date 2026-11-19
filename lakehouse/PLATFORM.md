# Historical DBQL telemetry

The platform domain imports the three CSVs consumed by the legacy
`warehouse/teradata/dbql/load.py` loader. It is a historical migration, not live
Spark query instrumentation. Raw bronze snapshots are dated with BUSINESS_DATE;
silver preserves the DBC columns, including CHAR padding and duplicate object
edges. Ref-based views use Delta snapshot isolation rather than ACCESS row locks.
See A-409 through A-411 for the explicit boundaries.

The daily graph has three readiness sensors, bronze_platform, dbt_platform and
parity_platform. Missing files time out at the sensor and fail immediately in the
ingestor; a header-only CSV is valid and produces an empty typed model. Inputs
must be immutable and atomically published for the duration of a run. The default
directory is `warehouse/teradata/dbql`; `PLATFORM_DBQL_LANDING` overrides it for
both local and Airflow readers. Use the same directory as the legacy loader's
`--root` argument. Snapshots across different tables are not a single transaction.

## Local build and parity

The emulator records live BTEQ operations in its DBC tables after loading the CSV
history. Therefore, after the warehouse chain, reload **only the historical DBQL
fixture** before comparing it with the same CSVs. Do not run more BTEQ operations
between reload and parity. The parity PostgreSQL reader connects directly and
does not append live telemetry. No live-row filters or query-ID exclusions hide
extra rows in these specs.

```sh
NS=sfx-d1110-before TD_PG_PORT=55395 PYTHONPATH=warehouse/teradata \
  warehouse/.venv/bin/python -m dbql.load
NS=sfx-d1110-after BUSINESS_DATE=20261109 SPARK_LOCAL_IP=127.0.0.1 \
  lakehouse/.venv/bin/python -m lakehouse.runtime.platform --business-date 20261109
NS=sfx-d1110-after BUSINESS_DATE=20261109 SPARK_LOCAL_IP=127.0.0.1 \
  lakehouse/.venv/bin/python -m lakehouse.runtime.dbt --select tag:platform
NS=sfx-d1110-after LEGACY_NS=sfx-d1110-before TD_PG_PORT=55395 \
  SPARK_LOCAL_IP=127.0.0.1 lakehouse/.venv/bin/python -m lakehouse.parity run \
  --business-date 20261109 --spec platform.dbc_qrylog platform.dbc_qrylogobjects \
  platform.dbc_tablesv platform.qrylogv platform.qrylogobjectsv platform.tablesv \
  platform.consumer_reads
```

The port above is the documented local `sfx-d1110-before` port; other namespaces
should derive their own port or use TD_PG_DSN. These commands only reset the local
fixture history, not source files or other domain tables.

## Report window and grouping

`gold_platform.consumer_reads` defaults to the literal legacy interval
`[2026-10-11 00:00:00, 2026-11-10 00:00:00)`. dbt vars `dbql_window_start` and
`dbql_window_end` override those bounds. For example, with the same environment
as the build above, the venv dbt CLI accepts:

```sh
NS=sfx-d1110-after BUSINESS_DATE=20261109 SPARK_LOCAL_IP=127.0.0.1 \
  LAKEHOUSE_DELTA_ROOT="$PWD/lakehouse/.data/sfx-d1110-after/delta" \
  lakehouse/.venv/bin/dbt build --project-dir lakehouse/dbt --profiles-dir lakehouse/dbt \
  --select tag:platform \
  --vars '{dbql_window_start: "2026-10-11 00:00:00", dbql_window_end: "2026-11-10 00:00:00"}'
```

The division stays 30.00 even when bounds change, matching the source expression.
Username groups are case-insensitive and trailing-space-insensitive, with a
lowercase representative; application/client groups retain case distinctions.
Report order is read_queries DESC, username ASC NULLS LAST; order inside ties is
unspecified. Consumers that require order must issue that ORDER BY when reading
the Delta table; storage file order is not a query contract. Parity uses exact
full-column occurrence-numbered multisets, including nullable report groups,
with no numeric tolerance. The seven default-window specs deliberately remain
fixed to the source window; custom-window builds need matching custom oracles.
