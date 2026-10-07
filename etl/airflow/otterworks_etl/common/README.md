# otterworks_etl.common

Conventions every OtterWorks ETL DAG uses. DAG files stay thin; they import from here.

```python
from otterworks_etl.common import LEGACY_SCHEDULES, get_logger, legacy_run_date, otterworks_dag_kwargs

logger = get_logger(__name__)

@dag(
    dag_id="otterworks_analytics_etl",
    schedule=LEGACY_SCHEDULES["otterworks_analytics_etl"],   # always explicit
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    **otterworks_dag_kwargs(tags=["analytics"]),
)
```

| Module | What it gives a DAG |
| --- | --- |
| `dag_defaults` | `default_args()` (owner `otterworks-data`, 3 retries, 5 min delay, exponential backoff capped at 30 min, `log_task_failure`), `otterworks_dag_kwargs()` (`max_active_runs=1`, `catchup=False`, `otterworks` tag), `LEGACY_SCHEDULES` (cron strings from `etl/crontab`) |
| `log` | `get_logger(__name__)`, `log_event(logger, "event", **fields)` (JSON message), `StructuredFormatter` (one JSON object per line) |
| `callbacks` | `log_task_failure`: emits one `task_failed` structured event. Email/Slack/PagerDuty are not wired (no real endpoints); add a notifier next to it and append it in `default_args()` when one exists |
| `run_date` | `legacy_run_date(context)`: the UTC day the run fires, i.e. the legacy scripts' `ds`, not Airflow's previous-interval `ds`. `dag_run.conf["run_date"]` overrides it for replays |
| `staging` | `staging_key()`, `stage_json(hook, bucket, key, payload)`, `load_staged_json()`: large intermediates go to S3 as gzip JSON; only the key goes through XCom |

Rules the test suite (`etl/airflow/tests`) enforces on every file in `dags/`: DagBag imports
with no errors; explicit `schedule=`; owner, tags and docs set; `max_active_runs=1`,
`catchup=False`; retries with backoff and the failure callback; and no hook, Connection or
Variable call at parse time (AST check plus a DagBag load that fails on any Connection or
Variable read). Run it with `etl/airflow/scripts/run-tests.sh` against the built image.
