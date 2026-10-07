from __future__ import annotations

import gzip
import io
import json
import os
import uuid

import pytest

from otterworks_etl.common import load_staged_json, stage_json, staging_key


class FakeS3Hook:
    """In-memory stand-in for the two S3Hook methods the staging helpers use."""

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def load_bytes(self, bytes_data, key, bucket_name=None, replace=False):
        if not replace and (bucket_name, key) in self.objects:
            raise ValueError("exists")
        self.objects[(bucket_name, key)] = bytes_data

    def get_key(self, key, bucket_name=None):
        body = self.objects[(bucket_name, key)]
        return type("Obj", (), {"get": lambda self: {"Body": io.BytesIO(body)}})()


def test_staging_key_is_deterministic_and_safe():
    key = staging_key(
        "otterworks_analytics_etl",
        "scheduled__2026-10-06T02:00:00+00:00",
        "extract_from_sqs",
        "events",
    )
    assert key == (
        "airflow-staging/otterworks_analytics_etl/scheduled__2026-10-06T02_00_00_00_00/"
        "extract_from_sqs/events.json.gz"
    )
    assert key == staging_key(
        "otterworks_analytics_etl",
        "scheduled__2026-10-06T02:00:00+00:00",
        "extract_from_sqs",
        "events",
    )


def test_staging_key_rejects_empty_segments():
    with pytest.raises(ValueError):
        staging_key("dag", "run", "///", "x")


def test_stage_and_load_roundtrip_with_fake_hook():
    hook = FakeS3Hook()
    payload = [{"eventType": "file_uploaded", "sizeBytes": 10}] * 1000
    key = stage_json(hook, "staging-bucket", "airflow-staging/a/b/c/events.json.gz", payload)
    body = hook.objects[("staging-bucket", key)]
    assert body[:2] == b"\x1f\x8b"
    assert json.loads(gzip.decompress(body)) == payload
    assert load_staged_json(hook, "staging-bucket", key) == payload
    # retry of the same task overwrites instead of failing
    stage_json(hook, "staging-bucket", key, payload)


def test_staged_bytes_are_reproducible():
    one, two = FakeS3Hook(), FakeS3Hook()
    stage_json(one, "b", "k", {"b": 1, "a": 2})
    stage_json(two, "b", "k", {"a": 2, "b": 1})
    assert one.objects == two.objects


@pytest.mark.skipif(
    not os.environ.get("OTTERWORKS_LOCALSTACK_URL"),
    reason="set OTTERWORKS_LOCALSTACK_URL to run against LocalStack",
)
def test_stage_and_load_roundtrip_with_s3hook_on_localstack(monkeypatch):
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook

    endpoint = os.environ["OTTERWORKS_LOCALSTACK_URL"]
    conn = {
        "conn_type": "aws",
        "login": "test",
        "password": "test",
        "extra": {"endpoint_url": endpoint, "region_name": "us-east-1"},
    }
    monkeypatch.setenv("AIRFLOW_CONN_OTTERWORKS_TEST_LOCALSTACK", json.dumps(conn))
    hook = S3Hook(aws_conn_id="otterworks_test_localstack")
    bucket = f"otterworks-etl-test-{uuid.uuid4().hex[:12]}"
    hook.create_bucket(bucket_name=bucket)
    try:
        key = staging_key("dag", "manual__2026-10-07", "task", "rows")
        payload = {"rows": list(range(500))}
        assert stage_json(hook, bucket, key, payload) == key
        assert hook.check_for_key(key, bucket_name=bucket)
        assert load_staged_json(hook, bucket, key) == payload
    finally:
        hook.delete_bucket(bucket_name=bucket, force_delete=True)
