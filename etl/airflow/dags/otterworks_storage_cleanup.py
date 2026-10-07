"""Daily storage cleanup (replaces etl/scripts/storage_cleanup_daily.py, cron 02:30 UTC).

Objects under ``storage_cleanup_files_prefix`` in the file storage bucket that no
``s3_key`` in ``storage_cleanup_metadata_table`` references are orphans: they are moved to
``<quarantine_bucket>/<storage_cleanup_quarantine_prefix>/<ds>/<key>`` and a storage report
is written to the data lake bucket.

Parity choices pinned by the goldens (etl/tests/golden/storage_cleanup_daily): ``s3_key`` is
matched by exact string, so case, leading-``/`` and ``s3://`` variants make a referenced file
an orphan; the report fields and rounding are legacy's. ``storage_cleanup_normalize_keys``
(default false) also matches a reference after stripping a leading ``/`` or an
``s3://<file storage bucket>/`` prefix; case is never folded. With it off the DAG logs how many
references normalization would have matched.

Quarantine is copy, verify the copy, then delete. A retry skips an object whose source is gone
and whose copy exists; a same-day copy is overwritten, as legacy does. A per-object failure is
logged at ERROR and the rest continue (legacy); the task then fails, with no retry, after
recording its counts, and ``generate_storage_report`` still writes the legacy report.

Listings, references and orphans above ``INLINE_LIMIT`` entries are staged in the data lake
bucket and only their key goes through XCom; staged objects are removed once a run succeeds and
kept when it fails. Run date: ``legacy_run_date``; replay a day with
``--conf '{"run_date": "YYYY-MM-DD"}'``.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import pendulum
from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.dynamodb import DynamoDBHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
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
from otterworks_etl.storage_cleanup import (
    build_report,
    find_orphans,
    object_record,
    quarantine_orphans,
    referenced_keys,
    scan_references,
)

DAG_ID = "otterworks_storage_cleanup"
AWS_CONN_ID = "aws_default"
INLINE_LIMIT = 1000
QUARANTINE_XCOM = "quarantine_result"
NORMALIZE_VARIABLE = "storage_cleanup_normalize_keys"

logger = get_logger(__name__)


def _staging_bucket() -> str:
    return Variable.get("data_lake_bucket")


def _bool_var(key: str) -> bool:
    value = Variable.get(key, deserialize_json=True)
    if not isinstance(value, bool):
        raise AirflowFailException(f"Variable {key}={value!r} is not JSON true or false")
    return value


def _run_prefix(context) -> str:
    return staging_key(DAG_ID, context["run_id"], "_x", "_x").rsplit("/", 2)[0] + "/"


def _hand_off(name: str, items: list, context) -> dict[str, Any]:
    """Small lists go inline through XCom; larger ones are staged and only the key is passed."""
    if len(items) <= INLINE_LIMIT:
        return {"items": items}
    key = staging_key(DAG_ID, context["run_id"], context["ti"].task_id, name)
    stage_json(S3Hook(aws_conn_id=AWS_CONN_ID), _staging_bucket(), key, items)
    return {"key": key}


def _receive(handoff: dict[str, Any], s3: S3Hook) -> list:
    if "key" in handoff:
        return load_staged_json(s3, _staging_bucket(), handoff["key"])
    return handoff["items"]


@dag(
    dag_id=DAG_ID,
    schedule=LEGACY_SCHEDULES[DAG_ID],
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    doc_md=__doc__,
    **otterworks_dag_kwargs(tags=["storage", "cleanup"]),
)
def otterworks_storage_cleanup():
    @task
    def list_s3_objects(**context) -> dict:
        bucket = Variable.get("file_storage_bucket")
        prefix = Variable.get("storage_cleanup_files_prefix")
        contents = S3Hook(aws_conn_id=AWS_CONN_ID).get_file_metadata(prefix, bucket_name=bucket)
        objects = [object_record(c) for c in contents]
        total_size_bytes = sum(o["size"] for o in objects)
        log_event(
            logger,
            "s3_objects_listed",
            location=f"s3://{bucket}/{prefix}",
            objects=len(objects),
            total_size_bytes=total_size_bytes,
        )
        return {
            **_hand_off("objects", objects, context),
            "total_objects": len(objects),
            "total_size_bytes": total_size_bytes,
        }

    @task
    def list_metadata_references(**context) -> dict:
        table_name = Variable.get("storage_cleanup_metadata_table")
        table = DynamoDBHook(aws_conn_id=AWS_CONN_ID).conn.Table(table_name)
        references = referenced_keys(scan_references(table))
        log_event(logger, "metadata_references_scanned", table=table_name, keys=len(references))
        return {**_hand_off("references", references, context), "references": len(references)}

    @task
    def find_orphaned_objects(listing: dict, references: dict, **context) -> dict:
        normalize = _bool_var(NORMALIZE_VARIABLE)
        bucket = Variable.get("file_storage_bucket")
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        result = find_orphans(
            _receive(listing, s3),
            _receive(references, s3),
            normalize=normalize,
            file_storage_bucket=bucket,
        )
        if normalize:
            log_event(
                logger,
                "references_normalized",
                variable=NORMALIZE_VARIABLE,
                matched=result.normalizable_references,
            )
        else:
            log_event(
                logger,
                "normalization_disabled",
                logging.WARNING if result.normalizable_references else logging.INFO,
                variable=NORMALIZE_VARIABLE,
                would_match=result.normalizable_references,
            )
        log_event(
            logger,
            "orphans_found",
            orphaned_objects=len(result.orphans),
            orphaned_bytes=result.orphaned_bytes,
            normalize_keys=normalize,
        )
        return {
            **_hand_off("orphans", result.orphans, context),
            "total_objects": listing["total_objects"],
            "total_size_bytes": listing["total_size_bytes"],
            "orphaned_objects": len(result.orphans),
            "orphaned_bytes": result.orphaned_bytes,
        }

    @task
    def move_to_quarantine(found: dict, **context) -> dict:
        ds = legacy_run_date(context)
        file_bucket = Variable.get("file_storage_bucket")
        quarantine_bucket = Variable.get("quarantine_bucket")
        prefix = Variable.get("storage_cleanup_quarantine_prefix")
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        result = quarantine_orphans(
            s3,
            _receive(found, s3),
            file_storage_bucket=file_bucket,
            quarantine_bucket=quarantine_bucket,
            quarantine_prefix=prefix,
            ds=ds,
        )
        counts = {
            "objects_quarantined": result.quarantined,
            "objects_failed": result.failed,
            "already_quarantined": result.already_quarantined,
            "quarantine_bucket": quarantine_bucket,
        }
        # Pushed before failing so generate_storage_report can still write the legacy report.
        context["ti"].xcom_push(key=QUARANTINE_XCOM, value=counts)
        log_event(
            logger,
            "quarantine_done",
            location=f"s3://{quarantine_bucket}/{prefix}/{ds}/",
            **counts,
        )
        if result.failed:
            raise AirflowFailException(
                "%d of %d orphans not quarantined (kept in s3://%s): %s"
                % (result.failed, found["orphaned_objects"], file_bucket, result.failed_keys[:10])
            )
        return counts

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def generate_storage_report(found: dict, **context) -> str:
        ds = legacy_run_date(context)
        counts = context["ti"].xcom_pull(task_ids="move_to_quarantine", key=QUARANTINE_XCOM)
        if not counts:
            raise AirflowFailException("move_to_quarantine recorded no result; no report written")
        report = build_report(
            ds=ds,
            generated_at=datetime.now(tz=UTC).isoformat(),
            total_objects=found["total_objects"],
            total_size_bytes=found["total_size_bytes"],
            orphaned_objects=found["orphaned_objects"],
            orphaned_bytes=found["orphaned_bytes"],
            objects_quarantined=counts["objects_quarantined"],
            objects_failed=counts["objects_failed"],
            quarantine_bucket=counts["quarantine_bucket"],
            price_per_gb_month_usd=float(Variable.get("storage_cleanup_price_per_gb_month_usd")),
        )
        bucket = Variable.get("data_lake_bucket")
        key = "{}/{}/report.json".format(Variable.get("storage_cleanup_report_prefix"), ds)
        S3Hook(aws_conn_id=AWS_CONN_ID).load_bytes(
            json.dumps(report, indent=2).encode("utf-8"), key=key, bucket_name=bucket, replace=True
        )
        log_event(
            logger,
            "storage_report_generated",
            location=f"s3://{bucket}/{key}",
            orphaned_objects=report["orphans"]["orphaned_objects"],
            objects_quarantined=report["cleanup"]["objects_quarantined"],
            objects_failed=report["cleanup"]["objects_failed"],
            storage_freed_gb=report["savings"]["storage_freed_gb"],
        )
        return key

    @task(trigger_rule=TriggerRule.NONE_FAILED)
    def cleanup_staging(**context) -> int:
        bucket = _staging_bucket()
        s3 = S3Hook(aws_conn_id=AWS_CONN_ID)
        keys = s3.list_keys(bucket_name=bucket, prefix=_run_prefix(context)) or []
        if keys:
            s3.delete_objects(bucket, keys)
        log_event(logger, "staging_cleaned", bucket=bucket, keys=len(keys))
        return len(keys)

    found = find_orphaned_objects(list_s3_objects(), list_metadata_references())
    quarantined = move_to_quarantine(found)
    report = generate_storage_report(found)
    cleanup = cleanup_staging()
    quarantined >> report >> cleanup
    quarantined >> cleanup


otterworks_storage_cleanup()
