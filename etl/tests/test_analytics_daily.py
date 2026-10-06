import gzip
import json
from datetime import datetime, timezone

import boto3
import psycopg2
import pytest
from botocore.exceptions import ClientError

from conftest import load_script

QUEUE_NAME = "otterworks-analytics"
TABLE_NAME = "otterworks-analytics-events"
BUCKET = "otterworks-data-lake"


def _today():
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


@pytest.fixture
def no_postgres(monkeypatch):
    def connect(**_):
        raise psycopg2.OperationalError("no database in unit tests")

    monkeypatch.setattr(psycopg2, "connect", connect)


def _queue(events):
    sqs = boto3.client("sqs", region_name="us-east-1")
    url = sqs.create_queue(QueueName=QUEUE_NAME)["QueueUrl"]
    for event in events:
        sqs.send_message(QueueUrl=url, MessageBody=json.dumps(event))
    return sqs, url


def _messages_left(sqs, url):
    attrs = sqs.get_queue_attributes(
        QueueUrl=url,
        AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
    )["Attributes"]
    return int(attrs["ApproximateNumberOfMessages"]) + int(attrs["ApproximateNumberOfMessagesNotVisible"])


def _table():
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "event_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return dynamodb


def _summary():
    ds = _today()
    key = "analytics/daily/year=%s/month=%s/day=%s/summary.json.gz" % (ds[:4], ds[5:7], ds[8:10])
    body = boto3.client("s3", region_name="us-east-1").get_object(Bucket=BUCKET, Key=key)["Body"].read()
    return json.loads(gzip.decompress(body))


EVENTS = [
    {"eventType": "document_created", "ownerId": "u1", "documentId": "d1"},
    {"eventType": "file_uploaded", "ownerId": "u2", "fileId": "f1", "sizeBytes": 10},
    {"eventType": "file_shared", "ownerId": "u2", "fileId": "f1"},
]


def test_sqs_events_survive_failure_before_data_lake_load(aws, etl_config, no_postgres):
    sqs, url = _queue(EVENTS)
    # DynamoDB table missing -> the run fails after draining SQS but before anything is persisted.

    with pytest.raises(ClientError):
        load_script("analytics_daily").main()

    assert _messages_left(sqs, url) == len(EVENTS)


def test_sqs_events_survive_data_lake_write_failure(aws, etl_config, no_postgres):
    sqs, url = _queue(EVENTS)
    _table()
    # Data lake bucket missing -> PutObject fails.

    with pytest.raises(ClientError):
        load_script("analytics_daily").main()

    assert _messages_left(sqs, url) == len(EVENTS)


def test_sqs_messages_deleted_after_successful_load(aws, etl_config, no_postgres):
    sqs, url = _queue(EVENTS)
    dynamodb = _table()
    dynamodb.put_item(
        TableName=TABLE_NAME,
        Item={"event_id": {"S": "e1"}, "event_date": {"S": _today()}, "eventType": {"S": "comment_added"}, "authorId": {"S": "u3"}},
    )
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)

    load_script("analytics_daily").main()

    assert _messages_left(sqs, url) == 0
    summary = _summary()
    assert summary["total_events"] == len(EVENTS) + 1
    assert summary["active_users"] == 3


def test_redelivered_message_counted_once(aws, etl_config, no_postgres, monkeypatch):
    sqs, url = _queue(EVENTS)
    _table()
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)

    real_client = boto3.client

    def client(service, *args, **kwargs):
        c = real_client(service, *args, **kwargs)
        if service == "sqs":
            real_receive = c.receive_message
            first = {}

            def receive_message(**kw):
                if "response" in first and not first.get("replayed"):
                    first["replayed"] = True
                    return first["response"]  # same messages delivered again (visibility timeout elapsed)
                response = real_receive(**kw)
                first.setdefault("response", response)
                return response

            c.receive_message = receive_message
        return c

    monkeypatch.setattr(boto3, "client", client)

    load_script("analytics_daily").main()

    assert _summary()["total_events"] == len(EVENTS)
    assert _messages_left(sqs, url) == 0


def test_receive_requests_visibility_timeout_covering_run(aws, etl_config, no_postgres, monkeypatch):
    _queue(EVENTS)
    _table()
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
    seen = []
    real_client = boto3.client

    def client(service, *args, **kwargs):
        c = real_client(service, *args, **kwargs)
        if service == "sqs":
            real_receive = c.receive_message

            def receive_message(**kw):
                seen.append(kw.get("VisibilityTimeout"))
                return real_receive(**kw)

            c.receive_message = receive_message
        return c

    monkeypatch.setattr(boto3, "client", client)

    load_script("analytics_daily").main()

    assert seen and all(v is not None and v >= 900 for v in seen)
