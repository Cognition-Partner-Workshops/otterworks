# Snowpark jobs

Each job owns `<job>.py` and exports `run(session)`. Invoke it using:

```
warehouse/.venv/bin/python warehouse/snowpark/run_job.py --job <job>
```

The shared runner creates the session on `__RUN_DATABASE___SNOWPARK_WH` with the JSON
Spark-act job tag. Read `SPARK_RAW_<AREA>.<TABLE>` for Spark-fixture parity and
write deterministic refreshes into `MART_SPARK`. Avoid module-import side effects
and unmanaged sessions. The registry's `command` should use this runner.
Bind only the provisioned `SNOWFLAKE_*` environment variables; the runner uses
`__RUN_DATABASE__` and rejects an out-of-scope database or warehouse.
