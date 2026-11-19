# Users conversion

The [ownership list](coverage/domains/users.yaml) declares 79 source-derived
IDs. The demo compares 39 logical outputs: 23 warehouse tables/views/extract
outputs, five Informatica targets, six Spark Parquet plus two JDBC outputs, and
three reports. Some source IDs share outputs; the coverage map links every
affected ID and all relevant checks. There is no users BI or partner extract in
the consumer registry. The users team export and the activity report are verified
as file contracts, not as a live service cutover.

## Reproduce against disposable data

Use a fresh metrics-free namespace and a local/disposable PostgreSQL with a DB
owner that can create `users_infa`. That database holds independent legacy
Informatica targets and Spark JDBC copies; do not reuse a production connection
or run multiple namespaces on the same oracle at once. This runs the demo fixture
for 2026-11-09. If running other dates, supply a matching set of legacy snapshots
and Spark landing files for that business date and confirm the latest pointer
state; neither a mutable PostgreSQL table nor a latest Parquet file is an as-of
snapshot.

```bash
export NS=users-after LEGACY_NS=users-before BUSINESS_DATE=20261109
make sfx-teradata-up NS="$LEGACY_NS" ROWS_PER_TABLE=2000 BUSINESS_DATE="$BUSINESS_DATE"
make lakehouse/.venv/.requirements
export TD_PG_PORT="$(python3 -c 'import os,zlib; print(54500+zlib.crc32(os.environ["LEGACY_NS"].encode())%1000)')"
export SPARK_LOCAL_IP=127.0.0.1
export TD_JDBC_URL="jdbc:postgresql://127.0.0.1:$TD_PG_PORT/users_infa" TD_JDBC_USER=postgres
bin=lakehouse/.venv/bin/python
"$bin" -m lakehouse.tests.users_infa_oracle --landing warehouse/landing --business-date "$BUSINESS_DATE"
make sfx-lakehouse-run SFX_LH_LANDING=warehouse/landing
landing="lakehouse/.data/$NS/users-extra"
python3 etl/spark/fixture/generate_fixture.py --rows 70 --seed 1110 --output "$landing/spark/$BUSINESS_DATE"
bash lakehouse/tests/users_spark_oracle.sh "$landing/spark/$BUSINESS_DATE"
"$bin" -m lakehouse.tests.users_activity_oracle --source "$landing/activity" --business-date "$BUSINESS_DATE"
for dag in lakehouse_users_spark lakehouse_users_activity; do
  "$bin" -m lakehouse.orchestration run --dag "$dag" --landing "$landing" --business-date "$BUSINESS_DATE"
done
make sfx-lakehouse-coverage
make sfx-lakehouse-test
make sfx-lakehouse-airflow-test SFX_LH_AF_DAG_TEST=0
```

Legacy and modern processing consume the same warehouse PSV, Spark PSV, and
report inputs. The report oracle executes unchanged legacy code against real
PostgreSQL and an isolated local S3 double. Output comparators check keys,
columns, nulls, duplicates, row-level values and per-column fingerprints. Except
for fixed-width padding and the narrow risk-score tolerance, values compare
directly; report `generated_at` is explicitly outside parity. An empty warehouse
preference target is expected because the executed chain stages it but never
populates it. The separate Spark preference output is nonempty and independently
verified. [Assumptions A-300–A-315](assumptions/assumptions.yaml) describe the
intentional differences and unresolved production choices.

## Shared integration handoff

- `informatica_workflow:SFX_CONTENT.wf_SFX_CONTENT_DAILY`
- `informatica_scheduler:SFX_CONTENT.wf_SFX_CONTENT_DAILY.Scheduler`
- `informatica_config:SFX_CONTENT.default_session_config`
- `informatica_task:SFX_CONTENT.wf_SFX_CONTENT_DAILY.Start`
- `batch_runner:etl/run.sh`
- `batch_runner:etl/spark/run.sh`
- `batch_runner:warehouse/teradata/jobs/daily_chain`
- `etl_config:etl/config.ini`
- `spark_config:etl/spark/conf/spark-defaults.conf`
- `spark_library:etl/spark/jobs/py/common/runtime.py`
- `spark_library:etl/spark/jobs/py/common/schemas.py`
- `spark_library:etl/spark/scala/src/main/scala/sfx/BatchSupport.scala`
- `bteq_script:warehouse/teradata/dbql/consumer_reads.bteq`
- `etl_script:etl/scripts/analytics_daily.py`
- `cron_entry:etl/crontab#f34723629b86`
- `cron_entry:warehouse/teradata/jobs/crontab.example#250f291ea0eb`
- `cron_entry:warehouse/teradata/jobs/daily_chain#stage=users/01_load_users`
- `cron_entry:warehouse/teradata/jobs/daily_chain#stage=users/02_load_teams`
- `cron_entry:warehouse/teradata/jobs/daily_chain#stage=users/03_load_identity`
- `cron_entry:warehouse/teradata/jobs/daily_chain#stage=users/04_load_events`
- `cron_entry:warehouse/teradata/jobs/daily_chain#stage=users/10_activity_daily`

Preserve the shared workflow dependencies: documents staging waits for the
app-user session and document shares wait for the role-grant session. Confirm the
writer of record, Spark JDBC consumers, activity staging/publication, and the
upstream schedules before activating the paused DAGs.
