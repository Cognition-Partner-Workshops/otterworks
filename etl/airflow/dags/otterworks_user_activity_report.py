"""Daily user activity report (replaces etl/scripts/user_activity_daily.py, cron 05:00 UTC).

Reads what ``otterworks_analytics_etl`` (02:00 UTC) writes: the ``analytics_daily_summary``
rows from PostgreSQL and the per-user ``top_users.jsonl.gz`` partitions from the data lake.
Ordering is time-based, as with cron, so each DAG can cut over on its own; an
``ExternalTaskSensor`` on the analytics DAG is a follow-up once both run on Airflow.

Run date: ``legacy_run_date`` (the UTC day the run fires); replay a day with
``--conf '{"run_date": "YYYY-MM-DD"}'``. Missing or unreadable day files are skipped, as legacy
did, and logged with their count; a missing bucket is fatal on write. ``user_summaries.jsonl``
is written before the dated report and ``latest/``. Only S3 keys go through XCom: the
summary rows and the rendered report are staged, the day files are read where they are.
Staged objects are removed once a run succeeds and kept when it fails.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pendulum
from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.trigger_rule import TriggerRule

from otterworks_etl.common import (
    LEGACY_SCHEDULES,
    get_logger,
    legacy_run_date,
    load_staged_json,
    log_event,
    otterworks_dag_kwargs,
    stage_json,
    staging_key,
)
from otterworks_etl.user_activity import (
    SUMMARY_SQL,
    UserActivity,
    accumulate_day,
    build_report,
    day_keys,
    is_missing_bucket,
    is_postgres_config_error,
    report_objects,
    summary_parameters,
    summary_records,
    summary_rows,
)

DAG_ID = "otterworks_user_activity_report"
AWS_CONN_ID = "aws_default"
POSTGRES_CONN_ID = "otterworks_postgres"

logger = get_logger(__name__)


def _bucket() -> str:
    return Variable.get("data_lake_bucket")


def _int_var(key: str) -> int:
    raw = Variable.get(key)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise AirflowFailException(f"Variable {key}={raw!r} is not an integer") from exc
    if value < 0:
        raise AirflowFailException(f"Variable {key}={value} must not be negative")
    return value


def _run_prefix(context) -> str:
    return staging_key(DAG_ID, context["run_id"], "_x", "_x").rsplit("/", 2)[0] + "/"


@contextmanager
def _writing_to(bucket: str) -> Iterator[None]:
    try:
        yield
    except Exception as exc:
        if is_missing_bucket(exc):
            raise AirflowFailException(f"bucket {bucket} does not exist: {exc}") from exc
        raise


def _day_exists(s3: S3Hook, bucket: str, key: str) -> bool:
    try:
        return s3.check_for_key(key, bucket_name=bucket)
    except Exception as exc:
        log_event(logger, "day_unreadable", key=f"s3://{bucket}/{key}", error=str(exc))
        return False


def _read_day(s3: S3Hook, bucket: str, key: str) -> bytes | None:
    try:
        return s3.get_key(key, bucket_name=bucket).get()["Body"].read()
    except Exception as exc:
        log_event(logger, "day_unreadable", key=f"s3://{bucket}/{key}", error=str(exc))
        return None


@dag(
    dag_id=DAG_ID,
    schedule=LEGACY_SCHEDULES[DAG_ID],
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    doc_md=__doc__,
    **otterworks_dag_kwargs(tags=["analytics", "reports"]),
)
def otterworks_user_activity_report():
    @task
    def query_analytics_aggregates(**context) -> dict:
        ds = legacy_run_date(context)
        lookback_days = _int_var("user_activity_lookback_days")
        try:
            records = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID).get_records(
                SUMMARY_SQL, parameters=summary_parameters(ds, lookback_days)
            )
        except Exception as exc:
            if is_postgres_config_error(exc):
                raise AirflowFailException(f"PostgreSQL query failed: {exc}") from exc
            raise
        rows = summary_rows(records)
        bucket = _bucket()
        key = staging_key(DAG_ID, context["run_id"], context["ti"].task_id, "daily_summaries")
        with _writing_to(bucket):
            stage_json(S3Hook(aws_conn_id=AWS_CONN_ID), bucket, key, rows)
        log_event(logger, "summaries_queried", ds=ds, lookback_days=lookback_days, rows=len(rows))
        return {"ds": ds, "lookback_days": lookback_days, "summaries_key": key}

    @task
    def query_per_user_activity(**context) -> dict:
        """Find which day partitions exist; stages nothing, so a failed run leaves no objects."""
        ds = legacy_run_date(context)
        lookback_days = _int_var("user_activity_lookback_days")
        bucket = _bucket()
        keys = day_keys(Variable.get("analytics_prefix"), ds, lookback_days)
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        present = [key for key in keys if _day_exists(s3, bucket, key)]
        log_event(
            logger,
            "user_activity_partitions",
            ds=ds,
            days_requested=len(keys),
            days_present=len(present),
            days_missing=len(keys) - len(present),
        )
        return {"ds": ds, "lookback_days": lookback_days, "day_keys": present}

    @task
    def generate_user_reports(summaries: dict, users: dict, **context) -> dict:
        if (summaries["ds"], summaries["lookback_days"]) != (users["ds"], users["lookback_days"]):
            raise AirflowFailException(
                f"queries disagree on run date or lookback: {summaries} vs {users}; clear the run"
            )
        bucket = _bucket()
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        ds = summaries["ds"]
        activity = UserActivity()
        unreadable = 0
        for key in users["day_keys"]:
            body = _read_day(s3, bucket, key)
            if body is None:
                unreadable += 1
            elif not accumulate_day(activity, body):
                log_event(logger, "day_file_ended_early", key=f"s3://{bucket}/{key}")
        report = build_report(
            summary_records(load_staged_json(s3, bucket, summaries["summaries_key"])),
            activity.users(),
            ds,
            datetime.now(tz=UTC).isoformat(),
            summaries["lookback_days"],
            max_user_summaries=_int_var("user_activity_max_user_summaries"),
            top_users=_int_var("user_activity_top_users"),
        )
        objects = report_objects(report, Variable.get("user_activity_report_prefix"), ds)
        key = staging_key(DAG_ID, context["run_id"], context["ti"].task_id, "report_objects")
        with _writing_to(bucket):
            stage_json(s3, bucket, key, objects)
        log_event(
            logger,
            "report_generated",
            ds=ds,
            days_read=activity.days_read,
            days_unreadable=unreadable,
            days_ended_early=activity.days_aborted,
            users=len(activity.totals),
            reporting_days=report["trends"]["reporting_days"],
            objects=len(objects),
        )
        return {"ds": ds, "objects_key": key}

    @task
    def store_reports_to_s3(generated: dict) -> list[str]:
        bucket = _bucket()
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        written = []
        for key, body in load_staged_json(s3, bucket, generated["objects_key"]):
            with _writing_to(bucket):
                s3.load_bytes(body.encode("utf-8"), key=key, bucket_name=bucket, replace=True)
            written.append(key)
        log_event(
            logger,
            "reports_stored",
            ds=generated["ds"],
            locations=[f"s3://{bucket}/{k}" for k in written],
        )
        return written

    @task(trigger_rule=TriggerRule.NONE_FAILED)
    def cleanup_staging(**context) -> int:
        bucket = _bucket()
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        keys = s3.list_keys(bucket_name=bucket, prefix=_run_prefix(context)) or []
        if keys:
            s3.delete_objects(bucket, keys)
        log_event(logger, "staging_cleaned", bucket=bucket, keys=len(keys))
        return len(keys)

    generated = generate_user_reports(query_analytics_aggregates(), query_per_user_activity())
    store_reports_to_s3(generated) >> cleanup_staging()


otterworks_user_activity_report()
