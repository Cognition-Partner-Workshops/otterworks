import gzip
import json
from datetime import datetime, timedelta, timezone

import boto3
import pytest
from boto3.dynamodb.table import BatchWriter

from conftest import load_script

TABLE_NAME = "otterworks-audit-events"
BUCKET = "otterworks-audit-archive"


def _setup(count):
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "event_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "event_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    old = (datetime.now(tz=timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with table.batch_writer() as writer:
        for i in range(count):
            writer.put_item(Item={"event_id": "evt-%03d" % i, "timestamp": old, "action": "login"})
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
    return table


def _archived_event_ids():
    s3 = boto3.client("s3", region_name="us-east-1")
    ids = set()
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET, Prefix="audit-archive/").get("Contents", [])]
    for key in keys:
        s3.restore_object(Bucket=BUCKET, Key=key, RestoreRequest={"Days": 1})
        body = gzip.decompress(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()).decode("utf-8")
        ids.update(json.loads(line)["event_id"] for line in body.splitlines() if line)
    return ids, keys


def test_same_day_rerun_after_partial_delete_keeps_every_archived_event(aws, etl_config, monkeypatch):
    table = _setup(30)
    real_exit = BatchWriter.__exit__
    calls = {"n": 0}

    def flaky_exit(self, exc_type, exc_value, tb):
        calls["n"] += 1
        if calls["n"] == 2:
            self._items_buffer.clear()
            raise RuntimeError("ProvisionedThroughputExceededException")
        return real_exit(self, exc_type, exc_value, tb)

    monkeypatch.setattr(BatchWriter, "__exit__", flaky_exit)
    load_script("audit_archive_weekly").main()
    monkeypatch.setattr(BatchWriter, "__exit__", real_exit)
    assert table.scan(Select="COUNT")["Count"] == 5

    load_script("audit_archive_weekly").main()

    ids, keys = _archived_event_ids()
    assert len(keys) == 2
    assert ids == {"evt-%03d" % i for i in range(30)}
    assert table.scan(Select="COUNT")["Count"] == 0


def test_compliance_report_points_at_this_runs_archive(aws, etl_config):
    _setup(3)

    load_script("audit_archive_weekly").main()

    s3 = boto3.client("s3", region_name="us-east-1")
    reports = s3.list_objects_v2(Bucket=BUCKET, Prefix="reports/compliance/audit-archive/")["Contents"]
    assert len(reports) == 1
    report = json.loads(s3.get_object(Bucket=BUCKET, Key=reports[0]["Key"])["Body"].read())
    _, keys = _archived_event_ids()
    assert report["results"]["archive_location"] == "s3://%s/%s" % (BUCKET, keys[0])
    assert report["results"]["events_deleted_from_source"] == 3


def test_no_old_events_exits_cleanly(aws, etl_config):
    _setup(0)

    with pytest.raises(SystemExit) as exc:
        load_script("audit_archive_weekly").main()

    assert exc.value.code == 0
