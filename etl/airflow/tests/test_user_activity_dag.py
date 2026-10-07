from __future__ import annotations

import ast
import gzip
import json
from datetime import date
from types import SimpleNamespace
from unittest import mock

import pytest
from airflow.exceptions import AirflowFailException
from airflow.models import Variable
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from botocore.exceptions import ClientError

from otterworks_etl.user_activity import SUMMARY_SQL
from tests.audit_fakes import FakeS3Client
from tests.conftest import DAGS_FOLDER

DAG_ID = "otterworks_user_activity_report"
DAG_FILE = DAGS_FOLDER / f"{DAG_ID}.py"
BUCKET = "otterworks-data-lake"
DS = "2026-03-15"

VARIABLES = {
    "data_lake_bucket": BUCKET,
    "analytics_prefix": "analytics/daily",
    "user_activity_lookback_days": "30",
    "user_activity_report_prefix": "reports/user-activity",
    "user_activity_max_user_summaries": "500",
    "user_activity_top_users": "20",
}

ROW = (date(2026, 3, 15), 2, 1, 1, 6, 1, 2, 0, 1, 1, 0, 100)


def test_task_graph(dagbag):
    dag = dagbag.dags[DAG_ID]
    assert dag.schedule_interval == "0 5 * * *"
    down = {t.task_id: set(t.downstream_task_ids) for t in dag.tasks}
    assert down == {
        "query_analytics_aggregates": {"generate_user_reports"},
        "query_per_user_activity": {"generate_user_reports"},
        "generate_user_reports": {"store_reports_to_s3"},
        "store_reports_to_s3": {"cleanup_staging"},
        "cleanup_staging": set(),
    }
    assert dag.get_task("cleanup_staging").trigger_rule == "none_failed"


def test_uses_provider_hooks_only_and_no_sensor():
    source = DAG_FILE.read_text()
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0] if isinstance(node, ast.Import) else (node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not {m for m in imported if m.split(".")[0] in {"boto3", "botocore", "psycopg2"}}
    assert ".get_records(" in source and "S3Hook" in source and ".load_bytes(" in source
    assert "put_object" not in source
    assert not any("sensor" in m for m in imported)


def _day(*users) -> bytes:
    return gzip.compress("\n".join(json.dumps(u) for u in users).encode())


class Env:
    """Fake S3 client, PostgresHook.get_records and Variables for direct task calls."""

    def __init__(self, dagbag, rows=(ROW,), buckets=(BUCKET,), pg_error=None, **variables):
        self.dag = dagbag.dags[DAG_ID]
        self.s3 = FakeS3Client()
        self.buckets = set(buckets)
        self.rows = list(rows)
        self.pg_error = pg_error
        self.queries = []
        self.writes = []
        self.variables = {**VARIABLES, **{k: str(v) for k, v in variables.items()}}
        self.context = {
            "run_id": "scheduled__2026-03-14T05:00:00+00:00",
            "dag_run": SimpleNamespace(conf={"run_date": DS}),
        }

    def __enter__(self):
        env = self

        def get_records(hook, sql, parameters=None):
            env.queries.append((hook.postgres_conn_id, sql, parameters))
            if env.pg_error is not None:
                raise env.pg_error
            return env.rows

        def load_bytes(hook, bytes_data, key, bucket_name=None, replace=False):
            if bucket_name not in env.buckets:
                raise ClientError({"Error": {"Code": "NoSuchBucket"}}, "PutObject")
            env.writes.append(key)
            env.s3.put(bucket_name, key, bytes_data)

        def check_for_key(hook, key, bucket_name=None):
            if bucket_name not in env.buckets:
                raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
            return (bucket_name, key) in env.s3.objects

        def get_key(hook, key, bucket_name=None):
            return SimpleNamespace(get=lambda: env.s3.get_object(Bucket=bucket_name, Key=key))

        def list_keys(hook, bucket_name=None, prefix=""):
            return [k for b, k in env.s3.objects if b == bucket_name and k.startswith(prefix)]

        def delete_objects(hook, bucket, keys):
            for k in keys:
                env.s3.objects.pop((bucket, k))

        self.patches = [
            mock.patch.object(Variable, "get", side_effect=lambda k, *a, **kw: env.variables[k]),
            mock.patch.object(PostgresHook, "get_records", get_records),
            mock.patch.object(S3Hook, "load_bytes", load_bytes),
            mock.patch.object(S3Hook, "check_for_key", check_for_key),
            mock.patch.object(S3Hook, "get_key", get_key),
            mock.patch.object(S3Hook, "list_keys", list_keys),
            mock.patch.object(S3Hook, "delete_objects", delete_objects),
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
        if task_id == "store_reports_to_s3":
            return task.python_callable(*args)
        return task.python_callable(*args, **ctx)

    def run(self):
        summaries = self.call("query_analytics_aggregates")
        users = self.call("query_per_user_activity")
        generated = self.call("generate_user_reports", summaries, users)
        written = self.call("store_reports_to_s3", generated)
        self.call("cleanup_staging")
        return written

    def body(self, key):
        return self.s3.objects[(BUCKET, key)]["body"].decode()


def test_full_run_writes_legacy_objects_jsonl_first_and_cleans_staging(dagbag):
    with Env(dagbag) as env:
        env.s3.put(
            BUCKET,
            "analytics/daily/year=2026/month=03/day=15/top_users.jsonl.gz",
            _day(
                {"user_id": "u1", "total": 2, "actions": {"edit": 2}},
                {"user_id": "u2", "total": 5, "actions": {"z": 1, "a": 4}},
            ),
        )
        env.s3.put(
            BUCKET,
            "analytics/daily/year=2026/month=02/day=13/top_users.jsonl.gz",
            _day({"user_id": "old", "total": 99}),
        )
        written = env.run()

    assert env.queries == [("otterworks_postgres", SUMMARY_SQL, (DS, 30, DS))]
    assert written == [
        "reports/user-activity/2026-03-15/user_summaries.jsonl",
        "reports/user-activity/2026-03-15/activity_report.json",
        "reports/user-activity/latest/activity_report.json",
    ]
    assert [k for k in env.writes if k.startswith("reports/")] == written
    assert not [k for _, k in env.s3.objects if k.startswith("airflow-staging/")]

    dated = env.body(written[1])
    assert dated == env.body(written[2])
    report = json.loads(dated)
    assert [u["user_id"] for u in report["user_summaries"]] == ["u2", "u1"]
    assert '"actions_by_type": {\n        "z": 1,\n        "a": 4\n      }' in dated
    assert report["daily_summaries"][0]["report_date"] == DS
    assert list(report["daily_summaries"][0])[:2] == ["report_date", "active_users"]
    assert report["trends"] == {
        "total_events": 6,
        "peak_active_users": 2,
        "avg_daily_events": 6.0,
        "reporting_days": 1,
    }
    assert env.body(written[0]).endswith("\n")
    assert env.body(written[0]).splitlines()[0].startswith('{"user_id": "u2", "total_actions": 5')


def test_variables_drive_lookback_prefixes_and_truncation(dagbag):
    with Env(
        dagbag,
        user_activity_lookback_days=2,
        analytics_prefix="lake/x",
        user_activity_report_prefix="r",
        user_activity_top_users=1,
        user_activity_max_user_summaries=1,
    ) as env:
        env.s3.put(
            BUCKET,
            "lake/x/year=2026/month=03/day=14/top_users.jsonl.gz",
            _day({"user_id": "a"}, {"user_id": "b", "total": 1}),
        )
        env.s3.put(
            BUCKET,
            "lake/x/year=2026/month=03/day=13/top_users.jsonl.gz",
            _day({"user_id": "c", "total": 9}),
        )
        written = env.run()
    assert env.queries[0][2] == (DS, 2, DS)
    report = json.loads(env.body("r/latest/activity_report.json"))
    assert written[0] == "r/2026-03-15/user_summaries.jsonl"
    assert report["lookback_days"] == 2
    assert [u["user_id"] for u in report["user_summaries"]] == ["b"]
    assert [u["user_id"] for u in report["top_users"]] == ["b"]


def test_empty_inputs_write_report_without_jsonl(dagbag):
    with Env(dagbag, rows=()) as env:
        written = env.run()
    assert written == [
        "reports/user-activity/2026-03-15/activity_report.json",
        "reports/user-activity/latest/activity_report.json",
    ]
    assert json.loads(env.body(written[0]))["trends"]["avg_daily_events"] == 0


def test_missing_bucket_is_silent_on_read_and_fatal_on_write(dagbag):
    with Env(dagbag, buckets=(), data_lake_bucket="missing") as env:
        with pytest.raises(AirflowFailException, match="does not exist"):
            env.call("query_analytics_aggregates")
        assert env.call("query_per_user_activity")["day_keys"] == []
    assert env.writes == []


def test_partition_lookup_stages_nothing_and_skips_missing_days(dagbag):
    with Env(dagbag, user_activity_lookback_days=3) as env:
        env.s3.put(BUCKET, "analytics/daily/year=2026/month=03/day=14/top_users.jsonl.gz", b"x")
        users = env.call("query_per_user_activity")
    assert users == {
        "ds": DS,
        "lookback_days": 3,
        "day_keys": ["analytics/daily/year=2026/month=03/day=14/top_users.jsonl.gz"],
    }
    assert env.writes == []


def test_unreadable_day_is_skipped(dagbag):
    key = "analytics/daily/year=2026/month=03/day=14/top_users.jsonl.gz"
    with Env(dagbag) as env:
        summaries = env.call("query_analytics_aggregates")
        users = {"ds": DS, "lookback_days": 30, "day_keys": [key]}
        generated = env.call("generate_user_reports", summaries, users)
        written = env.call("store_reports_to_s3", generated)
    assert len(written) == 2


def test_queries_must_agree_on_run_date_and_lookback(dagbag):
    with Env(dagbag) as env:
        summaries = env.call("query_analytics_aggregates")
        users = {"ds": DS, "lookback_days": 7, "day_keys": []}
        with pytest.raises(AirflowFailException, match="disagree"):
            env.call("generate_user_reports", summaries, users)


def test_postgres_config_error_fails_without_retry(dagbag):
    error = Exception('FATAL:  database "otterworks_missing" does not exist')
    with Env(dagbag, pg_error=error) as env:
        with pytest.raises(AirflowFailException, match="PostgreSQL query failed"):
            env.call("query_analytics_aggregates")
    assert env.writes == []


def test_transient_postgres_error_is_retried(dagbag):
    error = Exception("could not connect to server: Connection refused")
    with Env(dagbag, pg_error=error) as env:
        with pytest.raises(Exception, match="Connection refused") as info:
            env.call("query_analytics_aggregates")
    assert not isinstance(info.value, AirflowFailException)


def test_invalid_lookback_variable_fails(dagbag):
    with Env(dagbag, user_activity_lookback_days="thirty") as env:
        with pytest.raises(AirflowFailException, match="not an integer"):
            env.call("query_analytics_aggregates")


def test_failed_write_keeps_staging_for_a_retry(dagbag):
    with Env(dagbag) as env:
        summaries = env.call("query_analytics_aggregates")
        users = env.call("query_per_user_activity")
        generated = env.call("generate_user_reports", summaries, users)
        env.buckets.clear()
        with pytest.raises(AirflowFailException):
            env.call("store_reports_to_s3", generated)
        env.buckets.add(BUCKET)
        assert len(env.call("store_reports_to_s3", generated)) == 2
    assert [k for _, k in env.s3.objects if k.startswith("airflow-staging/")]
