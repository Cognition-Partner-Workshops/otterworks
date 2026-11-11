# Spark SQL job models

Each job owns `spark/<job>/`. Put SQL, schema tests and any job-specific macros
under that directory. Models materialize as tables in `SFX_D1110_AFTER.MART_SPARK`.
All 42 Spark input tables are declared in `staging/spark/sources.yml`:
`source('spark_billing', 'INVOICE_LINE')`, `source('spark_documents', 'DOCUMENT')`,
`source('spark_users', 'APP_USER')`, and `source('spark_audit', 'AUDIT_EVENT')`.
These point to isolated `SPARK_RAW_*` schemas, not the scaffold's `RAW_*` fixture.

Load the existing Spark fixture with
`warehouse/.venv/bin/python warehouse/snowflake/spark_landing.py`.
The loader checks CSV headers and row counts, uses content-addressed stage
prefixes, loads into temporary tables with `FORCE=TRUE`, and atomically replaces
each destination's rows with `INSERT OVERWRITE`. It does not change `RAW_*`,
COMPAT, their loaders, or their dbt sources. Loads carry job `_landing`.

A migrated registry command can be:

```
warehouse/.venv/bin/python warehouse/snowflake/run_dbt.py build --job <job> --select path:models/spark/<job>
```

`make sfx-spark-snowflake JOB=<job>` dispatches that command and supplies
`SFX_SPARK_JOB`. Airflow supplies the same variable. `run_dbt.py` propagates all
shared attribution fields plus `run`, `act` and `job` through `SFX_QUERY_TAG`.
The existing query-tag macro preserves extra keys while setting transform phase.
Credentials stay in the environment; the PEM is never written to a file.
