import configparser
import gzip
import json
from datetime import datetime, timezone
from unittest.mock import Mock

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import ANY, Stubber

from etl.scripts import analytics_daily


@pytest.fixture
def dailyJob(monkeypatch):
    config = configparser.ConfigParser()
    config.read_dict(
        {
            "aws": {"access_key": "test", "secret_key": "test", "region": "us-east-1"},
            "database": {
                "host": "localhost",
                "port": "5432",
                "database": "test",
                "user": "test",
                "password": "test",
            },
            "s3": {
                "data_lake_bucket": "test-data-lake",
                "data_lake_bucket_owner": "012345678901",
                "analytics_prefix": "analytics/daily",
            },
        }
    )
    monkeypatch.setattr(analytics_daily.configparser, "ConfigParser", lambda: config)
    monkeypatch.setattr(config, "read", Mock())
    monkeypatch.setattr(
        analytics_daily,
        "datetime",
        Mock(
            wraps=datetime,
            now=Mock(return_value=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        ),
    )
    s3 = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    sqs = Mock()
    sqs.receive_message.return_value = {}
    dynamo = Mock()
    dynamo.Table.return_value.scan.return_value = {
        "Items": [
            {
                "event_type": "document_created",
                "userId": "test-user",
                "documentId": "test-doc",
            }
        ]
    }
    client = Mock(side_effect={"sqs": sqs, "s3": s3}.__getitem__)
    monkeypatch.setattr(
        analytics_daily.boto3, "client", lambda service, **kwargs: client(service)
    )
    monkeypatch.setattr(analytics_daily.boto3, "resource", Mock(return_value=dynamo))
    connect = Mock()
    monkeypatch.setattr(analytics_daily.psycopg2, "connect", connect)
    return config, client, s3, connect


SUMMARY_PARAMS = {
    "Bucket": "test-data-lake",
    "Key": "analytics/daily/year=2026/month=01/day=02/summary.json.gz",
    "Body": ANY,
    "ExpectedBucketOwner": "012345678901",
}


def test_summary_upload_uses_configured_bucket_owner(dailyJob, monkeypatch):
    _, _, s3, connect = dailyJob
    putObject = Mock(wraps=s3.put_object)
    monkeypatch.setattr(s3, "put_object", putObject)
    with Stubber(s3) as stub:
        stub.add_response("put_object", {}, SUMMARY_PARAMS)
        for _ in range(3):
            stub.add_response("put_object", {})

        analytics_daily.main()

        stub.assert_no_pending_responses()
    payload = json.loads(gzip.decompress(putObject.call_args_list[0].kwargs["Body"]))
    assert payload["total_events"] == 1
    assert payload["documents_created"] == 1
    connect.return_value.commit.assert_called_once()


def test_summary_stops_when_s3_rejects_the_write(dailyJob, monkeypatch):
    _, _, s3, connect = dailyJob
    putObject = Mock(wraps=s3.put_object)
    monkeypatch.setattr(s3, "put_object", putObject)
    with Stubber(s3) as stub:
        stub.add_client_error(
            "put_object",
            service_error_code="AccessDenied",
            http_status_code=403,
            expected_params=SUMMARY_PARAMS,
        )
        with pytest.raises(ClientError) as error:
            analytics_daily.main()
        stub.assert_no_pending_responses()

    assert error.value.response["ResponseMetadata"]["HTTPStatusCode"] == 403
    putObject.assert_called_once()
    connect.assert_not_called()


@pytest.mark.parametrize(
    "owner", [None, "", "not-an-account", "123", "１２３４５６７８９０１２"]
)
def test_invalid_bucket_owner_stops_before_extracting_events(dailyJob, owner):
    config, client, _, _ = dailyJob
    if owner is None:
        config.remove_option("s3", "data_lake_bucket_owner")
    else:
        config.set("s3", "data_lake_bucket_owner", owner)

    with pytest.raises(ValueError, match="data_lake_bucket_owner"):
        analytics_daily.main()

    client.assert_not_called()
