"""Weekly audit archive (replaces etl/scripts/audit_archive_weekly.py, cron Sundays 03:00 UTC).

Audit events older than the retention (``audit_archive_retention_days``) are scanned from
DynamoDB, written to S3 as JSONL.gz in the archive storage class (GLACIER), deleted from
DynamoDB when ``audit_archive_delete_enabled`` is true, and summarized in a compliance report.
Only S3 keys and counts go through XCom; the scanned lines are staged in the archive bucket.

Parity choices pinned by the goldens (etl/tests/golden/audit_archive_weekly): the cutoff is
the legacy string comparison ``#ts < :cutoff``; Decimals encode as legacy; the compliance
fields stay hardcoded. Legacy deletes nothing (its key does not match the table's ``id`` key);
with the flag off (the default) the DAG deletes nothing either and logs what it would delete.

Destructive step: ``cleanup_dynamodb`` reads the archive back from S3 (restoring it from
GLACIER when needed), checks it is byte-for-byte the one ``compress_and_upload`` wrote, and
deletes by ``id`` only the events in it, in batches of at most 25. A retry after a partial
failure repeats that, so it never deletes an event that is not in the uploaded archive.

Run date: ``legacy_run_date``; replay a day with ``--conf '{"run_date": "YYYY-MM-DD"}'``.
Staged objects are removed once a run succeeds and kept when it fails.
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
from airflow.utils.trigger_rule import TriggerRule

from otterworks_etl.audit_archive import (
    ArchiveMismatchError,
    ArchiveOverwriteError,
    archive_key,
    build_report,
    check_key_schema,
    check_overwrite,
    compress_lines,
    cutoff_date,
    decompress_lines,
    delete_in_batches,
    delete_plan,
    encode_events,
    existing_object,
    read_object,
    scan_events,
    sha256_hex,
    verified_delete_plan,
)
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

DAG_ID = "otterworks_audit_archive"
AWS_CONN_ID = "aws_default"

logger = get_logger(__name__)


def _bucket() -> str:
    return Variable.get("archive_bucket")


def _int_var(key: str) -> int:
    return int(Variable.get(key))


def _bool_var(key: str) -> bool:
    value = Variable.get(key, deserialize_json=True)
    if not isinstance(value, bool):
        raise AirflowFailException(f"Variable {key}={value!r} is not JSON true or false")
    return value


def _run_prefix(context) -> str:
    return staging_key(DAG_ID, context["run_id"], "_x", "_x").rsplit("/", 2)[0] + "/"


def _cleanup_result(deleted: int, plan) -> dict:
    return {
        "deleted": deleted,
        "skipped_without_id": plan.skipped_without_id,
        "kept_within_retention": plan.kept_within_retention,
    }


def _table():
    return DynamoDBHook(aws_conn_id=AWS_CONN_ID).conn.Table(
        Variable.get("audit_archive_dynamodb_table")
    )


@dag(
    dag_id=DAG_ID,
    schedule=LEGACY_SCHEDULES[DAG_ID],
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    doc_md=__doc__,
    **otterworks_dag_kwargs(tags=["audit", "compliance"]),
)
def otterworks_audit_archive():
    @task
    def scan_audit_events(**context) -> dict:
        ds = legacy_run_date(context)
        retention_days = _int_var("audit_archive_retention_days")
        cutoff = cutoff_date(ds, retention_days)
        table = _table()
        lines = encode_events(scan_events(table, cutoff))
        log_event(
            logger,
            "audit_events_scanned",
            table=table.name,
            ds=ds,
            cutoff_date=cutoff,
            events=len(lines),
        )
        if not lines:
            log_event(logger, "no_events_to_archive", ds=ds, cutoff_date=cutoff)
            raise AirflowSkipException(f"no audit events older than {cutoff}")
        key = staging_key(DAG_ID, context["run_id"], context["ti"].task_id, "events")
        stage_json(S3Hook(aws_conn_id=AWS_CONN_ID), _bucket(), key, lines)
        return {
            "events_key": key,
            "events": len(lines),
            "ds": ds,
            "retention_days": retention_days,
            "cutoff_date": cutoff,
        }

    @task
    def compress_and_upload(scan: dict) -> dict:
        bucket = _bucket()
        storage_class = Variable.get("audit_archive_storage_class")
        staging = S3Hook(aws_conn_id=AWS_CONN_ID)
        lines = load_staged_json(staging, bucket, scan["events_key"])
        body = compress_lines(lines)
        key = archive_key(Variable.get("audit_archive_s3_prefix"), scan["ds"])

        client = staging.get_conn()
        if existing_object(client, bucket, key):
            existing = decompress_lines(read_object(client, bucket, key))
            try:
                check_overwrite(existing, lines)
            except ArchiveOverwriteError as exc:
                raise AirflowFailException(f"s3://{bucket}/{key}: {exc}") from exc

        S3Hook(aws_conn_id=AWS_CONN_ID, extra_args={"StorageClass": storage_class}).load_bytes(
            body, key=key, bucket_name=bucket, replace=True
        )
        log_event(
            logger,
            "archive_uploaded",
            location=f"s3://{bucket}/{key}",
            storage_class=storage_class,
            events=len(lines),
            compressed_size_bytes=len(body),
        )
        return {
            "archive_key": key,
            "sha256": sha256_hex(body),
            "storage_class": storage_class,
            "compressed_size_bytes": len(body),
            "events": len(lines),
        }

    @task
    def cleanup_dynamodb(scan: dict, upload: dict) -> dict:
        bucket = _bucket()
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        if not _bool_var("audit_archive_delete_enabled"):
            plan = delete_plan(
                load_staged_json(s3, bucket, scan["events_key"]), scan["cutoff_date"]
            )
            log_event(
                logger,
                "delete_disabled",
                logging.WARNING,
                variable="audit_archive_delete_enabled",
                would_delete=len(plan.keys),
                skipped_without_id=plan.skipped_without_id,
                kept_within_retention=plan.kept_within_retention,
            )
            return _cleanup_result(0, plan)

        batch_size = _int_var("audit_archive_delete_batch_size")
        table = _table()
        try:
            check_key_schema(table)
            plan = verified_delete_plan(
                s3.get_conn(), bucket, upload["archive_key"], upload["sha256"], scan["cutoff_date"]
            )
        except (ArchiveMismatchError, ValueError) as exc:
            raise AirflowFailException(f"nothing deleted: {exc}") from exc
        if plan.skipped_without_id or plan.kept_within_retention:
            log_event(
                logger,
                "delete_skipped",
                logging.WARNING,
                skipped_without_id=plan.skipped_without_id,
                kept_within_retention=plan.kept_within_retention,
            )

        def on_batch(index: int, size: int) -> None:
            log_event(logger, "delete_batch", table=table.name, batch=index, items=size)

        deleted = delete_in_batches(table, plan.keys, batch_size, on_batch)
        log_event(
            logger,
            "dynamodb_cleaned",
            table=table.name,
            deleted=deleted,
            skipped_without_id=plan.skipped_without_id,
            kept_within_retention=plan.kept_within_retention,
        )
        return _cleanup_result(deleted, plan)

    @task
    def generate_compliance_report(scan: dict, upload: dict, cleanup: dict) -> str:
        bucket = _bucket()
        report = build_report(
            ds=scan["ds"],
            generated_at=datetime.now(tz=UTC).isoformat(),
            retention_days=scan["retention_days"],
            cutoff=scan["cutoff_date"],
            events_archived=upload["events"],
            events_deleted=cleanup["deleted"],
            bucket=bucket,
            key=upload["archive_key"],
            storage_class=upload["storage_class"],
            compressed_size=upload["compressed_size_bytes"],
        )
        key = "{}/{}/report.json".format(Variable.get("audit_archive_report_prefix"), scan["ds"])
        S3Hook(aws_conn_id=AWS_CONN_ID).load_bytes(
            json.dumps(report, indent=2).encode("utf-8"), key=key, bucket_name=bucket, replace=True
        )
        log_event(
            logger,
            "compliance_report_generated",
            location=f"s3://{bucket}/{key}",
            archived=upload["events"],
            deleted=cleanup["deleted"],
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

    scan = scan_audit_events()
    upload = compress_and_upload(scan)
    cleanup = cleanup_dynamodb(scan, upload)
    generate_compliance_report(scan, upload, cleanup) >> cleanup_staging()


otterworks_audit_archive()
