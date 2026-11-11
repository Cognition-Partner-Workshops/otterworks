# Spark batch estate

## Local execution

Requirements: Docker Compose, Python 3, curl, Java 17 and uv. Tests install
PySpark 3.5.3 and PyYAML 6.0.2 through uv; they do not require Docker or PostgreSQL.
Ubuntu's libzstd1 is used to read the compressed history.

```sh
make sfx-spark-up
make sfx-spark-run
make sfx-spark-run JOB=billing_gl_trial_balance
make sfx-spark-test
make sfx-spark-down
```

Defaults: `NS=sfx-d1110-before`, `ROWS_PER_TABLE=200000`,
`SPARK_JOBS=30`. `SPARK_JOBS=N` runs the first N entries of jobs.txt;
`JOB=<id>` selects one entry, including docs_folder_legacy_report.
The runner continues after a failed submission and returns nonzero if any fail.
Down removes the Compose volumes; bind-mounted files remain.

Up downloads the PostgreSQL JDBC and Scala compiler jars from the Google Maven
Central mirror, generates landing data and binary documents, loads PostgreSQL,
compiles the Scala jar in the Spark container, and copies packaged history logs
to the runtime event-log directory. Pull the configured Spark 3.5.3 and PostgreSQL
16 images before the first run; Compose does not pull them.

Host ports can be changed before up:

| Variable | Default | Endpoint |
| --- | --- | --- |
| SFX_SPARK_MASTER_PORT | 7077 | Spark master |
| SFX_SPARK_MASTER_UI_PORT | 8080 | Master web UI |
| SFX_SPARK_HISTORY_PORT | 18080 | History Server and /api/v1/applications |
| SFX_TDEMU_PORT | 55432 | PostgreSQL |

Runtime files are under `etl/spark/.data/`: `landing/` contains PSV tables and
`documents/FILE_OBJECT_BLOBS/`; `lake/<area>/<job>/` contains parquet output;
`logs/` contains submission output; `eventlogs/` is read by History Server.
Jars, compiled classes and common.zip are under `etl/spark/.cache/`.
These two directories are not versioned.

## Input and database configuration

If `warehouse/seed/generate.py` exists, up invokes it with `--rows` and
`--seed 1110` and mounts `warehouse/landing`. Otherwise it invokes
`fixture/generate_fixture.py` and mounts `etl/spark/.data/landing`.
Both layouts use `<area>/<TABLE>/<yyyymmdd>.psv`, with a header and pipe separator.
Table definitions are in `jobs/py/common/schemas.py`.

`SFX_SPARK_LANDING=/absolute/path` overrides the directory mounted by Make.
When using a different generator, populate that directory with the same table
layout. In container jobs, `LANDING_DIR` defaults to `/opt/landing` and
`LAKE_DIR` defaults to `/opt/lake`; these variables also support local-mode runs.

The PostgreSQL emulator database is `sfx_teradata`, with schemas
`sfx_billing`, `sfx_documents`, `sfx_users`, and `sfx_audit`.
JDBC settings are `TD_JDBC_URL`, `TD_JDBC_USER`, and `TD_JDBC_PASSWORD`.
Compose explicitly sets them; edit its environment block to use another endpoint.
The local loader operates on the Compose PostgreSQL service. A different JDBC
implementation also requires its driver jar and the matching driver setting in
`jobs/py/common/runtime.py` and `scala/src/main/scala/sfx/BatchSupport.scala`.

## History

Packaged logs are in `history/eventlogs/`. To recompute or verify their baseline:

```sh
python3 etl/spark/history/compute_baseline.py
python3 etl/spark/history/compute_baseline.py --check
```

`--log-dir` and `--output` select other paths. The inventory must contain exactly
one completed application per jobs.txt entry. Executor lifetime totals exclude
the driver and stop at application end. Task totals include failed attempts.
Output file counts come from final SQL accumulator values when available.

To set the report date relative to the other packaged applications:

```sh
python3 etl/spark/history/shift_eventlog.py etl/spark/history/eventlogs --days 118
```

The default selection is docs_folder_legacy_report. Repeating this command against
the same set of applications leaves the date unchanged. Recompute the baseline
after changing logs. Restart the Compose history service after replacing runtime
logs.

## Kubernetes manifests

`k8s/kustomization.yaml` includes 30 SparkApplication resources, namespace,
service account, namespaced RBAC and a shared workspace claim. Nothing is applied
by the Make targets. An existing Spark Operator supporting
`sparkoperator.k8s.io/v1beta2` is required to use these files.

The workspace claim requires a ReadWriteMany storage class. Populate its root with
the contents of etl/spark, including .cache/common.zip, the compiled Scala jar,
JDBC jars, and the .data/landing, .data/lake and .data/eventlogs directories.
Supply the referenced sfx-d1110-jdbc object with a password entry and a PostgreSQL
service reachable as sfx-tdemu, or adjust the JDBC environment references.
Driver and executor pods mount the same workspace. Scheduling remains in
etl/crontab; no ScheduledSparkApplication resources are included.
