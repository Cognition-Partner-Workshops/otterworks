# security_alert_anomaly — sfg1120

## Decision: retire

A case-insensitive repository-wide search for `security_alert_anomaly`,
`audit/security_alert_anomaly`, and `SPARK_ALERT_ANOMALY` found no consumers of
either the parquet or JDBC output. `warehouse/snowpark/security_alert_anomaly.py`
is another producer, not a reader. The registry and classification describe the
producer; migration metadata is not an output consumer. In particular,
`migration/dw-exit/manifest.yaml` has `output_relations: []`, inventory.csv has
zero outgoing edges, and lineage.md only declares the job node. No other Spark
job, warehouse model, or documentation references a read of these outputs.
External consumers were not checked.

The retirement removes both cron entries, the submit wrapper, and the Kubernetes
application. The registry remains as a retired tombstone, matching classification;
the Kubernetes kustomization remains empty. Historical source and existing outputs
are preserved. No output refresh, append, or deletion is performed after retirement.
The repeated uncached RDD scans disappear from scheduled execution rather than
being optimized for an unused output. No shared template or compose changes.

PR #3259 was reviewed as a migration precedent but not reused: retirement avoids
all compute, and its proposed partitioning would unnecessarily change the unused
output's layout.

## Local measurements

200,000 rows per fixture table, Spark 3.5.3. Legacy source was copied with
`git show origin/demo-snowflake-dw-exit:etl/spark/jobs/py/security_alert_anomaly.py`
into spark-master `/tmp/sfg1120-security_alert_anomaly.py`. Three sequential
submissions used the original wrapper's arguments: 900m executor memory, one core,
two requested executors, 96m Python worker memory, and common.zip. History Server
reports six actual executors per run. Measurements use `measure.py:spark_measure`
against http://localhost:18080, excluding the packaged November 10 baseline.

| State/run | Application | Runtime seconds | Executor-hours |
| --- | --- | ---: | ---: |
| Legacy 1 | app-20261120170259-0000 | 14.927 | 0.013922500 |
| Legacy 2 | app-20261120170316-0001 | 11.790 | 0.013393611 |
| Legacy 3 | app-20261120170330-0002 | 11.948 | 0.012972500 |
| **Legacy median** | | **11.948** | **0.013393611** |
| Retired check 1 | No application | N/A | 0 |
| Retired check 2 | No application | N/A | 0 |
| Retired check 3 | No application | N/A | 0 |
| **Retired median** | | **N/A** | **0** |

All three legacy runs had zero failed tasks and zero spill. After retirement,
three explicit `JOB=security_alert_anomaly bash etl/spark/run.sh` attempts exited 2
with `Unknown JOB: security_alert_anomaly`, as expected. Selection wall times were
0.071643, 0.073656, and 0.075541 seconds (not Spark runtimes). Each check compared
History Server application IDs, SHA-256 hashes of all lake output files, and JDBC
row count plus ordered row-content checksum before/after: no applications or
output changes. Thus zero executor-hours is avoided compute, not an event-log
measurement of a nonexistent application. There is no template-after application
or after screenshot because this job is retired.

## Validation

`RUN_TOKEN=sfx1120 make sfx-spark-test`:

```text
Ran 55 tests in 39.792s

OK
LOCAL_JOBS billing_revenue_by_plan docs_tag_normalize user_pref_json_flatten: OK (2000 rows)
SCALA_IDS IntegerType, LongType (>2^31), empty inputs and missing columns: OK
python3 etl/spark/history/compute_baseline.py --check
Baseline matches 30 applications.
```

New assertions cover the real job's retired registry/classification, removed
scheduling/submit resources, empty Kubernetes stub, and template rejection.
Existing runner tests cover empty selection and rejection of retired jobs.

## Environment notes and evidence

- Run tag is sfg1120; runtime token is **sfx1120** because run_config.py rejects
  sfg-prefixed tokens. Shared naming validation was not changed.
- Images were pulled first. Fixture startup needed the documented 900-second
  compose retry with identical environment after the 120-second Make timeout.
- common/package.py also imports warehouse.run_config; the documented copy into
  master and both workers is needed even for packaging, not just template submit.
- Fixture initialization creates root-owned cache directories. Packaging on the
  host raised PermissionError, so packaging ran as root inside spark-master.
- History Server includes packaged baseline apps alongside new ones; filter by
  the new application IDs when measuring.
- Full local logs, measurement script, and JSON are in
  `/home/ubuntu/shared_files/sfg1120-security-alert-anomaly/`.
- Legacy History Server screenshots (not after screenshots):
  `app-20261120170330-0002-jobs.png` and
  `app-20261120170330-0002-stage.png` in that evidence directory.
