from __future__ import annotations

import ast
import gzip
import json
import sys
from types import SimpleNamespace
from unittest import mock

import pytest
from airflow.exceptions import AirflowFailException
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.dynamodb import DynamoDBHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

from tests.conftest import DAGS_FOLDER
from tests.storage_fakes import FakeS3, FakeTable

DAG_ID = "otterworks_storage_cleanup"
DAG_FILE = DAGS_FOLDER / f"{DAG_ID}.py"
FILES = "otterworks-file-storage"
QUARANTINE = "otterworks-file-quarantine"
LAKE = "otterworks-data-lake"
REPORT = "reports/storage-cleanup/2026-06-01/report.json"

VARIABLES = {
    "file_storage_bucket": FILES,
    "quarantine_bucket": QUARANTINE,
    "data_lake_bucket": LAKE,
    "storage_cleanup_files_prefix": "files/",
    "storage_cleanup_metadata_table": "otterworks-file-metadata",
    "storage_cleanup_quarantine_prefix": "quarantined",
    "storage_cleanup_report_prefix": "reports/storage-cleanup",
    "storage_cleanup_price_per_gb_month_usd": "0.023",
    "storage_cleanup_normalize_keys": "false",
}


def test_task_graph(dagbag):
    dag = dagbag.dags[DAG_ID]
    assert dag.schedule_interval == "30 2 * * *"
    down = {t.task_id: set(t.downstream_task_ids) for t in dag.tasks}
    assert down["list_s3_objects"] == {"find_orphaned_objects"}
    assert down["list_metadata_references"] == {"find_orphaned_objects"}
    assert down["find_orphaned_objects"] == {"move_to_quarantine", "generate_storage_report"}
    assert down["move_to_quarantine"] == {"generate_storage_report", "cleanup_staging"}
    assert down["generate_storage_report"] == {"cleanup_staging"}
    assert dag.get_task("generate_storage_report").trigger_rule == "all_done"
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
    assert "DynamoDBHook" in source and "S3Hook" in source
    assert "put_object" not in source


class FakeTI:
    def __init__(self, store, task_id):
        self.store = store
        self.task_id = task_id

    def xcom_push(self, key, value):
        self.store[(self.task_id, key)] = value

    def xcom_pull(self, task_ids, key):
        return self.store.get((task_ids, key))


class Env:
    """Patches the hooks and Variables the DAG uses onto one fake S3 and table."""

    def __init__(self, dagbag, objects, references, **variables):
        self.dag = dagbag.dags[DAG_ID]
        self.s3 = FakeS3(FILES, QUARANTINE, LAKE)
        for key, body in objects.items():
            self.s3.put(FILES, key, body)
        self.table = FakeTable([{"id": i, "s3_key": r} for i, r in enumerate(references)])
        self.variables = {**VARIABLES, **{k: str(v) for k, v in variables.items()}}
        self.xcom = {}
        self.context = {
            "run_id": "manual__2026-06-01T02:30:00+00:00",
            "dag_run": SimpleNamespace(conf={"run_date": "2026-06-01"}),
        }

    def _variable(self, key, default_var=None, deserialize_json=False):
        value = self.variables[key]
        return json.loads(value) if deserialize_json else value

    def __enter__(self):
        s3 = self.s3
        methods = [
            "get_file_metadata",
            "head_object",
            "copy_object",
            "delete_objects",
            "load_bytes",
            "get_key",
            "list_keys",
        ]
        self.patches = [
            mock.patch.object(Variable, "get", side_effect=self._variable),
            mock.patch.object(
                DynamoDBHook,
                "conn",
                new_callable=mock.PropertyMock,
                return_value=SimpleNamespace(Table=lambda name: self.table),
            ),
            *(
                mock.patch.object(S3Hook, m, lambda hook, *a, _m=m, **kw: getattr(s3, _m)(*a, **kw))
                for m in methods
            ),
        ]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()

    def call(self, task_id, *args):
        task = self.dag.get_task(task_id)
        ctx = {**self.context, "ti": FakeTI(self.xcom, task_id)}
        return task.python_callable(*args, **ctx)

    def run(self):
        listing = self.call("list_s3_objects")
        references = self.call("list_metadata_references")
        found = self.call("find_orphaned_objects", listing, references)
        try:
            self.call("move_to_quarantine", found)
        finally:
            self.report_key = self.call("generate_storage_report", found)
        self.call("cleanup_staging")
        return found

    def report(self):
        return json.loads(self.s3.buckets[LAKE][REPORT]["body"])


OBJECTS = {
    "files/kept.txt": "kept",
    "files/user-bob/leading.txt": "slash",
    "files/user-carol/uri.txt": "uri",
    "files/user-alice/Report.PDF": "case",
    "files-archive/old.txt": "outside the prefix",
}
REFERENCES = [
    "files/kept.txt",
    "/files/user-bob/leading.txt",
    "s3://otterworks-file-storage/files/user-carol/uri.txt",
    "files/user-alice/report.pdf",
    "",
]


def test_flag_off_matches_exactly_and_logs_what_normalization_would_match(dagbag, caplog):
    with Env(dagbag, OBJECTS, REFERENCES) as env, caplog.at_level("INFO"):
        env.run()
    assert env.s3.keys(FILES) == ["files-archive/old.txt", "files/kept.txt"]
    assert env.s3.keys(QUARANTINE) == [
        "quarantined/2026-06-01/files/user-alice/Report.PDF",
        "quarantined/2026-06-01/files/user-bob/leading.txt",
        "quarantined/2026-06-01/files/user-carol/uri.txt",
    ]
    (event,) = (
        json.loads(r.message) for r in caplog.records if "normalization_disabled" in r.message
    )
    assert event["would_match"] == 2 and event["variable"] == "storage_cleanup_normalize_keys"
    report = env.report()
    assert report["inventory"]["total_objects"] == 4
    assert report["orphans"]["orphaned_objects"] == 3
    assert report["orphans"]["orphan_percentage"] == 75.0
    assert report["cleanup"] == {
        "objects_quarantined": 3,
        "objects_failed": 0,
        "quarantine_bucket": QUARANTINE,
    }
    assert env.s3.keys(LAKE) == [REPORT]


def test_flag_on_keeps_slash_and_uri_references_and_still_quarantines_case(dagbag):
    with Env(dagbag, OBJECTS, REFERENCES, storage_cleanup_normalize_keys="true") as env:
        env.run()
    assert env.s3.keys(QUARANTINE) == ["quarantined/2026-06-01/files/user-alice/Report.PDF"]
    assert "files/user-bob/leading.txt" in env.s3.keys(FILES)
    assert "files/user-carol/uri.txt" in env.s3.keys(FILES)
    assert env.report()["cleanup"]["objects_quarantined"] == 1


def test_invalid_flag_value_fails(dagbag):
    with Env(dagbag, OBJECTS, REFERENCES, storage_cleanup_normalize_keys='"yes"') as env:
        listing = env.call("list_s3_objects")
        references = env.call("list_metadata_references")
        with pytest.raises(AirflowFailException):
            env.call("find_orphaned_objects", listing, references)


def test_large_listings_are_staged_and_cleaned_up(dagbag, monkeypatch):
    objects = {"files/bulk/%04d.txt" % i: "x" for i in range(12)}
    references = ["files/bulk/%04d.txt" % i for i in range(0, 12, 2)]
    with Env(dagbag, objects, references) as env:
        callable_module = env.dag.get_task("list_s3_objects").python_callable.__module__
        monkeypatch.setattr(sys.modules[callable_module], "INLINE_LIMIT", 5)
        listing = env.call("list_s3_objects")
        refs = env.call("list_metadata_references")
        found = env.call("find_orphaned_objects", listing, refs)
        assert set(listing) == {"key", "total_objects", "total_size_bytes"}
        assert "key" in refs and "key" in found
        staged = json.loads(gzip.decompress(env.s3.buckets[LAKE][listing["key"]]["body"]))
        assert len(staged) == 12
        env.call("move_to_quarantine", found)
        env.call("generate_storage_report", found)
        assert env.call("cleanup_staging") == 3
    assert env.s3.keys(LAKE) == [REPORT]
    assert len(env.s3.keys(QUARANTINE)) == 6


def test_failed_copies_fail_the_task_after_the_rest_and_the_report_is_still_written(dagbag):
    with Env(dagbag, OBJECTS, REFERENCES) as env:
        env.s3.fail_copy = {"files/user-bob/leading.txt"}
        with pytest.raises(AirflowFailException, match="1 of 3 orphans not quarantined"):
            env.run()
    assert "files/user-bob/leading.txt" in env.s3.keys(FILES)
    assert len(env.s3.keys(QUARANTINE)) == 2
    report = env.report()
    assert report["cleanup"]["objects_quarantined"] == 2
    assert report["cleanup"]["objects_failed"] == 1
    assert report["orphans"]["orphaned_objects"] == 3


def test_missing_quarantine_bucket_keeps_legacy_report(dagbag):
    with Env(dagbag, OBJECTS, REFERENCES, quarantine_bucket="missing") as env:
        with pytest.raises(AirflowFailException):
            env.run()
    assert len(env.s3.keys(FILES)) == 5
    report = env.report()
    assert report["cleanup"] == {
        "objects_quarantined": 0,
        "objects_failed": 3,
        "quarantine_bucket": "missing",
    }
    assert report["savings"]["storage_freed_gb"] == 0.0


def test_retry_after_a_crash_produces_the_same_final_state(dagbag):
    with Env(dagbag, OBJECTS, REFERENCES) as env:
        listing = env.call("list_s3_objects")
        found = env.call("find_orphaned_objects", listing, env.call("list_metadata_references"))
        env.s3.fail_delete = {"files/user-carol/uri.txt"}
        with pytest.raises(AirflowFailException):
            env.call("move_to_quarantine", found)
        counts = env.call("move_to_quarantine", found)
        env.call("generate_storage_report", found)
    assert counts["objects_quarantined"] == 3 and counts["already_quarantined"] == 2
    assert env.s3.keys(FILES) == ["files-archive/old.txt", "files/kept.txt"]
    assert env.report()["cleanup"]["objects_quarantined"] == 3


def test_report_without_a_quarantine_result_fails(dagbag):
    with Env(dagbag, OBJECTS, REFERENCES) as env:
        listing = env.call("list_s3_objects")
        found = env.call("find_orphaned_objects", listing, env.call("list_metadata_references"))
        with pytest.raises(AirflowFailException, match="no report written"):
            env.call("generate_storage_report", found)
    assert env.s3.keys(LAKE) == []
