"""Daily analytics ETL (replaces etl/scripts/analytics_daily.py, cron 02:00 UTC).

SQS events (no date filter, as legacy) and DynamoDB events for the run date are staged to S3,
aggregated with pandas, then written to the data lake and upserted into
``analytics_daily_summary`` in parallel; the report follows. Only S3 keys go through XCom.

Run date: ``legacy_run_date`` (the UTC day the run fires); replay a day with
``--conf '{"run_date": "YYYY-MM-DD"}'``. Bodies that are not JSON are left in flight, as
legacy did (no DLQ yet, ETL-103), and logged as a WARNING with their count. Staged objects
are removed once a run succeeds and kept when it fails, so a retry or clear resumes from them.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pendulum
from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException, AirflowSkipException
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.dynamodb import DynamoDBHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.amazon.aws.hooks.sqs import SqsHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.trigger_rule import TriggerRule

from otterworks_etl.analytics import (
    NonObjectEventError,
    aggregate_events,
    build_report,
    data_lake_objects,
    drain_queue,
    native_dynamodb_item,
    upsert_parameters,
)
from otterworks_etl.analytics.transform import UPSERT_SQL
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

DAG_ID = "otterworks_analytics_etl"
AWS_CONN_ID = "aws_default"
POSTGRES_CONN_ID = "otterworks_postgres"

logger = get_logger(__name__)


def _bucket() -> str:
    return Variable.get("data_lake_bucket")


def _int_var(key: str) -> int:
    return int(Variable.get(key))


def _run_prefix(context) -> str:
    return staging_key(DAG_ID, context["run_id"], "_x", "_x").rsplit("/", 2)[0] + "/"


def _task_staging_prefix(context, task_id: str) -> str:
    return staging_key(DAG_ID, context["run_id"], task_id, "_x").rsplit("/", 1)[0] + "/"


def _is_auth_failure(exc: Exception) -> bool:
    # SQLSTATE 28P01/28000; psycopg2 has no pgcode on connect errors, so match the message.
    text = str(exc).lower()
    return getattr(exc, "pgcode", None) in {"28P01", "28000"} or (
        "authentication failed" in text or "no pg_hba.conf entry" in text
    )


@dag(
    dag_id=DAG_ID,
    schedule=LEGACY_SCHEDULES[DAG_ID],
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    doc_md=__doc__,
    **otterworks_dag_kwargs(tags=["analytics"]),
)
def otterworks_analytics_etl():
    @task
    def extract_from_sqs(**context) -> list[str]:
        bucket = _bucket()
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        sqs = SqsHook(aws_conn_id=AWS_CONN_ID).conn
        queue_url = sqs.get_queue_url(QueueName=Variable.get("analytics_sqs_queue_name"))[
            "QueueUrl"
        ]
        task_id = context["ti"].task_id

        # A retry keeps the batches an earlier attempt staged (their messages are deleted).
        earlier = sorted(
            s3.list_keys(bucket_name=bucket, prefix=_task_staging_prefix(context, task_id)) or []
        )
        resumed = sum(len(load_staged_json(s3, bucket, key)) for key in earlier)

        def stage_batch(index: int, events: list) -> str:
            key = staging_key(DAG_ID, context["run_id"], task_id, "batch-%05d" % index)
            return stage_json(s3, bucket, key, events)

        result = drain_queue(
            sqs,
            queue_url,
            stage_batch,
            max_messages=_int_var("analytics_sqs_max_messages"),
            batch_size=_int_var("analytics_sqs_batch_size"),
            wait_time_seconds=_int_var("analytics_sqs_wait_time_seconds"),
            max_consecutive_errors=_int_var("analytics_sqs_max_consecutive_errors"),
            messages_processed=resumed,
            next_batch=len(earlier),
        )
        log_event(
            logger,
            "sqs_extracted",
            queue_url=queue_url,
            events=result.events,
            resumed_events=resumed,
            malformed=result.malformed,
            messages_processed=result.messages_processed,
            batches=len(earlier) + len(result.staged_keys),
        )
        return earlier + result.staged_keys

    @task
    def extract_from_dynamodb(**context) -> str | None:
        ds = legacy_run_date(context)
        table_name = Variable.get("analytics_dynamodb_table")
        table = DynamoDBHook(aws_conn_id=AWS_CONN_ID).conn.Table(table_name)
        scan_kwargs = {
            "FilterExpression": "begins_with(event_date, :ds)",
            "ExpressionAttributeValues": {":ds": ds},
        }
        events = []
        while True:
            response = table.scan(**scan_kwargs)
            events.extend(native_dynamodb_item(item) for item in response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key
        log_event(logger, "dynamodb_extracted", table=table_name, ds=ds, events=len(events))
        if not events:
            return None
        key = staging_key(DAG_ID, context["run_id"], context["ti"].task_id, "events")
        return stage_json(S3Hook(aws_conn_id=AWS_CONN_ID), _bucket(), key, events)

    @task
    def transform_events(sqs_keys: list[str], dynamodb_key: str | None, **context) -> str:
        ds = legacy_run_date(context)
        bucket = _bucket()
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        events = [e for key in sqs_keys for e in load_staged_json(s3, bucket, key)]
        if dynamodb_key:
            events.extend(load_staged_json(s3, bucket, dynamodb_key))
        try:
            aggregates = aggregate_events(events)
        except NonObjectEventError as exc:
            # Data, not a transient error: retrying cannot help. The staged events are kept.
            raise AirflowFailException(
                f"{exc}; staged events kept under s3://{bucket}/{_run_prefix(context)}"
            ) from exc
        if aggregates is None:
            log_event(logger, "no_events", logging.WARNING, ds=ds)
            raise AirflowSkipException(f"no events for {ds}")
        log_event(
            logger,
            "aggregated",
            ds=ds,
            total_events=aggregates["summary"]["total_events"],
            active_users=aggregates["summary"]["active_users"],
        )
        key = staging_key(DAG_ID, context["run_id"], context["ti"].task_id, "aggregates")
        return stage_json(s3, bucket, key, aggregates)

    @task
    def load_to_data_lake(aggregates_key: str, **context) -> list[str]:
        ds = legacy_run_date(context)
        bucket = _bucket()
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        aggregates = load_staged_json(s3, bucket, aggregates_key)
        objects = data_lake_objects(aggregates, Variable.get("analytics_prefix"), ds)
        for key, body in objects.items():
            s3.load_bytes(body, key=key, bucket_name=bucket, replace=True)
        log_event(logger, "data_lake_loaded", bucket=bucket, keys=sorted(objects))
        return sorted(objects)

    @task
    def update_postgres_aggregates(aggregates_key: str, **context) -> None:
        ds = legacy_run_date(context)
        aggregates = load_staged_json(S3Hook(aws_conn_id=AWS_CONN_ID), _bucket(), aggregates_key)
        try:
            PostgresHook(postgres_conn_id=POSTGRES_CONN_ID).run(
                UPSERT_SQL, parameters=upsert_parameters(aggregates["summary"], ds)
            )
        except Exception as exc:
            if _is_auth_failure(exc):
                # A wrong credential does not fix itself; fail now instead of retrying.
                raise AirflowFailException(f"PostgreSQL rejected the credentials: {exc}") from exc
            raise
        log_event(logger, "postgres_upserted", table="analytics_daily_summary", ds=ds)

    @task
    def generate_report(aggregates_key: str, **context) -> str:
        ds = legacy_run_date(context)
        bucket = _bucket()
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        aggregates = load_staged_json(s3, bucket, aggregates_key)
        report = build_report(
            aggregates,
            ds,
            generated_at=datetime.now(tz=UTC).isoformat(),
            top_n=_int_var("analytics_report_top_users"),
        )
        key = "{}/{}/report.json".format(Variable.get("analytics_report_prefix"), ds)
        s3.load_bytes(
            json.dumps(report, indent=2).encode("utf-8"), key=key, bucket_name=bucket, replace=True
        )
        log_event(
            logger,
            "report_generated",
            key=key,
            total_events=report["summary"]["total_events"],
            active_users=report["summary"]["active_users"],
        )
        return key

    @task(trigger_rule=TriggerRule.NONE_FAILED)
    def cleanup_staging(**context) -> int:
        bucket = _bucket()
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        keys = s3.list_keys(bucket_name=bucket, prefix=_run_prefix(context)) or []
        if keys:
            s3.delete_objects(bucket, keys)
        log_event(logger, "staging_cleaned", bucket=bucket, keys=len(keys))
        return len(keys)

    sqs_keys = extract_from_sqs()
    dynamodb_key = extract_from_dynamodb()
    aggregates_key = transform_events(sqs_keys, dynamodb_key)
    loaded = [load_to_data_lake(aggregates_key), update_postgres_aggregates(aggregates_key)]
    report = generate_report(aggregates_key)
    loaded >> report >> cleanup_staging()


otterworks_analytics_etl()
