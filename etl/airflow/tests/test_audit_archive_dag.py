from __future__ import annotations

import ast
import json
from types import SimpleNamespace
from unittest import mock

import pytest
from airflow.exceptions import AirflowFailException, AirflowSkipException
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.dynamodb import DynamoDBHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

from tests.audit_fakes import FakeS3Client, FakeTable
from tests.conftest import DAGS_FOLDER

DAG_ID = "otterworks_audit_archive"
DAG_FILE = DAGS_FOLDER / f"{DAG_ID}.py"
BUCKET = "otterworks-audit-archive"
OLD = "2025-09-01T00:00:00Z"

VARIABLES = {
    "archive_bucket": BUCKET,
    "audit_archive_dynamodb_table": "otterworks-audit-events",
    "audit_archive_retention_days": "90",
    "audit_archive_s3_prefix": "audit-archive",
    "audit_archive_storage_class": "GLACIER",
    "audit_archive_report_prefix": "reports/compliance/audit-archive",
    "audit_archive_delete_batch_size": "25",
    "audit_archive_delete_enabled": "false",
}


def test_task_graph(dagbag):
    dag = dagbag.dags[DAG_ID]
    assert dag.schedule_interval == "0 3 * * 0"
    down = {t.task_id: set(t.downstream_task_ids) for t in dag.tasks}
    assert down["scan_audit_events"] == {
        "compress_and_upload",
        "cleanup_dynamodb",
        "generate_compliance_report",
    }
    assert down["compress_and_upload"] == {"cleanup_dynamodb", "generate_compliance_report"}
    assert down["cleanup_dynamodb"] == {"generate_compliance_report"}
    assert down["generate_compliance_report"] == {"cleanup_staging"}
    assert dag.get_task("cleanup_staging").trigger_rule == "none_failed"


def test_uses_provider_hooks_only():
    source = DAG_FILE.read_text()
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0] if isinstance(node, ast.Import) else (node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not {m for m in imported if m.split(".")[0] in {"boto3", "botocore"}}
    assert "DynamoDBHook" in source and "S3Hook" in source and ".load_bytes(" in source
    assert "put_object" not in source


class Env:
    """Patches the hooks and Variables the DAG uses onto one fake table and S3 client."""

    def __init__(self, dagbag, items, **variables):
        self.dag = dagbag.dags[DAG_ID]
        self.table = FakeTable(items, page_size=7)
        self.s3 = FakeS3Client()
        self.uploads = []
        self.variables = {**VARIABLES, **{k: str(v) for k, v in variables.items()}}
        self.context = {
            "run_id": "scheduled__2026-03-15T03:00:00+00:00",
            "dag_run": SimpleNamespace(conf={"run_date": "2026-03-15"}),
        }

    def _variable(self, key, default_var=None, deserialize_json=False):
        value = self.variables[key]
        return json.loads(value) if deserialize_json else value

    def __enter__(self):
        env = self

        def load_bytes(hook, bytes_data, key, bucket_name=None, replace=False):
            storage = (hook.extra_args or {}).get("StorageClass", "STANDARD")
            env.uploads.append((key, storage))
            env.s3.put(bucket_name, key, bytes_data, storage)

        def get_key(hook, key, bucket_name=None):
            return SimpleNamespace(get=lambda: env.s3.get_object(Bucket=bucket_name, Key=key))

        def list_keys(hook, bucket_name=None, prefix=""):
            return [k for b, k in env.s3.objects if b == bucket_name and k.startswith(prefix)]

        def delete_objects(hook, bucket, keys):
            for k in keys:
                env.s3.objects.pop((bucket, k))

        self.patches = [
            mock.patch.object(Variable, "get", side_effect=self._variable),
            mock.patch.object(
                DynamoDBHook,
                "conn",
                new_callable=mock.PropertyMock,
                return_value=SimpleNamespace(Table=lambda name: env.table),
            ),
            mock.patch.object(S3Hook, "get_conn", lambda hook: env.s3),
            mock.patch.object(S3Hook, "load_bytes", load_bytes),
            mock.patch.object(S3Hook, "get_key", get_key),
            mock.patch.object(S3Hook, "list_keys", list_keys),
            mock.patch.object(S3Hook, "delete_objects", delete_objects),
            mock.patch("otterworks_etl.audit_archive.archive.time.sleep", lambda s: None),
        ]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()

    def call(self, task_id, *args):
        task = self.dag.get_task(task_id)
        ctx = {**self.context, "ti": SimpleNamespace(task_id=task_id)}
        if task_id in {"scan_audit_events", "cleanup_staging"}:
            return task.python_callable(**ctx)
        return task.python_callable(*args)

    def run_until_cleanup(self):
        scan = self.call("scan_audit_events")
        upload = self.call("compress_and_upload", scan)
        return scan, upload


def _old(i, **extra):
    return {"id": "o-%03d" % i, "event_id": "o-%03d" % i, "timestamp": OLD, **extra}


KEEP = [
    {"id": "boundary", "event_id": "boundary", "timestamp": "2025-12-15T00:00:00Z"},
    {"id": "newer", "event_id": "newer", "timestamp": "2026-03-01T00:00:00Z"},
]


def test_flag_off_deletes_nothing_and_logs_the_count(dagbag, caplog):
    items = [_old(i) for i in range(30)] + KEEP
    with Env(dagbag, items) as env, caplog.at_level("WARNING"):
        scan, upload = env.run_until_cleanup()
        cleanup = env.call("cleanup_dynamodb", scan, upload)
        report_key = env.call("generate_compliance_report", scan, upload, cleanup)
        env.call("cleanup_staging")
    assert cleanup == {"deleted": 0, "skipped_without_id": 0, "kept_within_retention": 0}
    assert len(env.table.items) == 32 and env.s3.restores == []
    (event,) = (json.loads(r.message) for r in caplog.records if "delete_disabled" in r.message)
    assert event["would_delete"] == 30
    report = json.loads(env.s3.objects[(BUCKET, report_key)]["body"])
    assert report["results"]["events_deleted_from_source"] == 0
    assert report["results"]["events_archived"] == 30
    assert env.uploads[1] == (upload["archive_key"], "GLACIER")
    assert sorted(k for _, k in env.s3.objects) == sorted([upload["archive_key"], report_key])


def test_flag_on_deletes_archived_ids_in_batches_and_keeps_the_rest(dagbag):
    items = [_old(i) for i in range(30)] + KEEP + [{"event_id": "no-id", "timestamp": OLD}]
    with Env(dagbag, items, audit_archive_delete_enabled="true") as env:
        scan, upload = env.run_until_cleanup()
        cleanup = env.call("cleanup_dynamodb", scan, upload)
    assert cleanup == {"deleted": 30, "skipped_without_id": 1, "kept_within_retention": 0}
    assert env.table.batches == [25, 5]
    assert env.s3.restores == [upload["archive_key"]]
    assert env.table.ids() == ["boundary", "newer", None]


def test_retry_after_partial_failure_never_deletes_unarchived_events(dagbag):
    items = [_old(i) for i in range(60)] + KEEP
    with Env(dagbag, items, audit_archive_delete_enabled="true") as env:
        scan, upload = env.run_until_cleanup()
        # Written after the scan, older than the cutoff: not in the archive.
        env.table.items.append(_old(900))
        env.table.fail_flush = {1}
        with pytest.raises(Exception, match="ProvisionedThroughput"):
            env.call("cleanup_dynamodb", scan, upload)
        assert 25 < len(env.table.deleted_keys) < 60
        retry = env.call("cleanup_dynamodb", scan, upload)
    assert retry["deleted"] == 60
    archived = {"o-%03d" % i for i in range(60)}
    assert set(env.table.deleted_keys) == archived
    assert env.table.ids() == ["boundary", "newer", "o-900"]


def test_flag_on_refuses_a_replaced_archive(dagbag):
    items = [_old(i) for i in range(3)]
    with Env(dagbag, items, audit_archive_delete_enabled="true") as env:
        scan, upload = env.run_until_cleanup()
        env.s3.put(BUCKET, upload["archive_key"], b"\x1f\x8b not ours", "GLACIER")
        with pytest.raises(AirflowFailException, match="nothing deleted"):
            env.call("cleanup_dynamodb", scan, upload)
    assert len(env.table.items) == 3 and env.table.flushes == 0


def test_rerun_refuses_to_overwrite_an_archive_with_more_events(dagbag):
    items = [_old(i) for i in range(3)]
    with Env(dagbag, items) as env:
        env.run_until_cleanup()
        env.table.items.pop(0)
        scan = env.call("scan_audit_events")
        with pytest.raises(AirflowFailException, match="RUNBOOK"):
            env.call("compress_and_upload", scan)
        # Same events again (a retry): overwrite is allowed.
        env.table.items.insert(0, _old(0))
        env.call("compress_and_upload", env.call("scan_audit_events"))


def test_no_old_events_skips_and_writes_nothing(dagbag):
    with Env(dagbag, KEEP) as env:
        with pytest.raises(AirflowSkipException):
            env.call("scan_audit_events")
    assert env.s3.objects == {}


def test_invalid_flag_value_fails(dagbag):
    with Env(dagbag, [_old(1)], audit_archive_delete_enabled='"yes"') as env:
        scan, upload = env.run_until_cleanup()
        with pytest.raises(AirflowFailException):
            env.call("cleanup_dynamodb", scan, upload)
