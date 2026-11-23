"""python:S7608 — analytics_daily.py must pin the data-lake bucket owner on the
hourly-breakdown upload so a same-named bucket in another account is refused.

S3 enforces the x-amz-expected-bucket-owner header with Access Denied; LocalStack 3.8
accepts cross-account writes but does not enforce the header, so the LocalStack case
asserts the header reaches S3 on the wire.

Run: uv run --python 3.9 --with-requirements etl/requirements.txt --with numpy==1.21.6 \
     --with pytest python -m pytest etl/tests
The LocalStack case needs the local stack (`make infra-up`) and is skipped otherwise.
"""

import configparser
import importlib.util
import json
import os
import socket
import time
import urllib.parse
import uuid
from pathlib import Path
from unittest import mock

import boto3
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analytics_daily.py"
LOCALSTACK = os.environ.get("LOCALSTACK_ENDPOINT", "http://localhost:4566")
ETL_ACCOUNT = "000000000000"
OTHER_ACCOUNT = "111111111111"
HOURLY_SUFFIX = "hourly_breakdown.json.gz"


def load_script():
    spec = importlib.util.spec_from_file_location("analytics_daily", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_config(tmp_path, bucket, owner, access_key="test"):
    config = configparser.ConfigParser()
    config["aws"] = {
        "access_key": access_key,
        "secret_key": "test",
        "region": "us-east-1",
    }
    config["database"] = {
        "host": "127.0.0.1",
        "port": "1",
        "database": "x",
        "user": "x",
        "password": "x",
    }
    config["s3"] = {
        "data_lake_bucket": bucket,
        "data_lake_bucket_owner": owner,
        "analytics_prefix": "analytics/daily",
    }
    path = tmp_path / "config.ini"
    with open(path, "w") as fh:
        config.write(fh)
    return path


def use_config(path):
    original = configparser.ConfigParser.read
    return mock.patch.object(
        configparser.ConfigParser,
        "read",
        lambda self, _ignored, *a, **k: original(self, str(path)),
    )


def sample_event():
    return {
        "eventType": "document_edited",
        "userId": "u-1",
        "documentId": "d-1",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
    }


def test_hourly_breakdown_upload_pins_bucket_owner(tmp_path):
    s3 = mock.MagicMock()
    sqs = mock.MagicMock()
    sqs.receive_message.side_effect = [
        {
            "Messages": [
                {
                    "Body": json.dumps(sample_event()),
                    "MessageId": "1",
                    "ReceiptHandle": "r",
                }
            ]
        },
        {},
    ]
    dynamodb = mock.MagicMock()
    dynamodb.Table.return_value.scan.return_value = {"Items": []}
    clients = {"s3": s3, "sqs": sqs}

    with (
        use_config(write_config(tmp_path, "otterworks-data-lake", "123456789012")),
        mock.patch("boto3.client", side_effect=lambda name, **_: clients[name]),
        mock.patch("boto3.resource", return_value=dynamodb),
        mock.patch("psycopg2.connect"),
    ):
        load_script().main()

    hourly = [
        c.kwargs
        for c in s3.put_object.call_args_list
        if c.kwargs["Key"].endswith(HOURLY_SUFFIX)
    ]
    assert len(hourly) == 1
    assert hourly[0]["Bucket"] == "otterworks-data-lake"
    assert hourly[0].get("ExpectedBucketOwner") == "123456789012"


def localstack_up():
    try:
        url = urllib.parse.urlsplit(LOCALSTACK)
        socket.create_connection((url.hostname, url.port or 80), timeout=2).close()
        return True
    except OSError:
        return False


def local_client(service, account):
    return boto3.client(
        service,
        endpoint_url=LOCALSTACK,
        region_name="us-east-1",
        aws_access_key_id=account,
        aws_secret_access_key="test",
    )


def run_against_localstack(tmp_path, bucket, owner):
    real_client, real_resource = boto3.client, boto3.resource
    sent = []

    def record(request, **_):
        sent.append(request)

    def client(name, **kwargs):
        made = real_client(name, endpoint_url=LOCALSTACK, **kwargs)
        made.meta.events.register("before-send.s3.PutObject", record)
        return made

    def resource(name, **kwargs):
        return real_resource(name, endpoint_url=LOCALSTACK, **kwargs)

    seed_events()
    with (
        use_config(write_config(tmp_path, bucket, owner, access_key=ETL_ACCOUNT)),
        mock.patch("boto3.client", side_effect=client),
        mock.patch("boto3.resource", side_effect=resource),
    ):
        load_script().main()
    return sent


def seed_events():
    ddb = local_client("dynamodb", ETL_ACCOUNT)
    try:
        ddb.create_table(
            TableName="otterworks-analytics-events",
            KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "event_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
    except ddb.exceptions.ResourceInUseException:
        pass
    event = sample_event()
    ddb.put_item(
        TableName="otterworks-analytics-events",
        Item={
            "event_id": {"S": str(uuid.uuid4())},
            "event_date": {"S": event["timestamp"][:10]},
            **{k: {"S": v} for k, v in event.items()},
        },
    )


def keys(bucket, account):
    resp = local_client("s3", account).list_objects_v2(Bucket=bucket)
    return [o["Key"] for o in resp.get("Contents", [])]


@pytest.mark.skipif(not localstack_up(), reason="LocalStack not reachable")
def test_hourly_breakdown_to_foreign_bucket_carries_owner_check(tmp_path):
    bucket = f"otterworks-data-lake-{uuid.uuid4().hex[:8]}"
    local_client("s3", OTHER_ACCOUNT).create_bucket(Bucket=bucket)

    sent = run_against_localstack(tmp_path, bucket, ETL_ACCOUNT)

    hourly = [r for r in sent if r.url.split("?")[0].endswith(HOURLY_SUFFIX)]
    assert len(hourly) == 1
    owner = hourly[0].headers.get("x-amz-expected-bucket-owner")
    assert owner in (ETL_ACCOUNT, ETL_ACCOUNT.encode())


@pytest.mark.skipif(not localstack_up(), reason="LocalStack not reachable")
def test_hourly_breakdown_lands_in_owned_bucket(tmp_path):
    bucket = f"otterworks-data-lake-{uuid.uuid4().hex[:8]}"
    local_client("s3", ETL_ACCOUNT).create_bucket(Bucket=bucket)

    run_against_localstack(tmp_path, bucket, ETL_ACCOUNT)

    assert [k for k in keys(bucket, ETL_ACCOUNT) if k.endswith(HOURLY_SUFFIX)]
