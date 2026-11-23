from configparser import ConfigParser
from unittest.mock import Mock, patch

import boto3
import pytest
from botocore.stub import ANY, Stubber

from etl.scripts import analytics_daily

BUCKET = "test-data-lake"
BUCKET_OWNER = "123456789012"


@pytest.fixture
def etl_config(monkeypatch):
    config = ConfigParser()
    config.read_dict({
        "aws": {"access_key": "testing", "secret_key": "testing", "region": "us-east-1"},
        "database": {"host": "localhost", "port": "5432", "database": "etl", "user": "etl", "password": "testing"},
        "s3": {
            "data_lake_bucket": BUCKET,
            "analytics_prefix": "analytics",
            "data_lake_expected_bucket_owner": BUCKET_OWNER,
        },
    })
    monkeypatch.setattr(analytics_daily.configparser, "ConfigParser", lambda: config)
    monkeypatch.setattr(config, "read", Mock())
    return config


@pytest.mark.parametrize("owner", [None, "", "not-an-account-id"])
def test_invalid_bucket_owner_stops_before_extracting(monkeypatch, etl_config, owner):
    if owner is None:
        etl_config.remove_option("s3", "data_lake_expected_bucket_owner")
    else:
        etl_config.set("s3", "data_lake_expected_bucket_owner", owner)
    createClient = Mock()
    monkeypatch.setattr(analytics_daily.boto3, "client", createClient)
    with pytest.raises(ValueError, match="data_lake_expected_bucket_owner"):
        analytics_daily.main()
    createClient.assert_not_called()


def test_top_users_upload_checks_bucket_owner(monkeypatch, etl_config):
    sqs = Mock()
    sqs.receive_message.return_value = {}
    dynamodb = Mock()
    dynamodb.Table.return_value.scan.return_value = {
        "Items": [{"userId": "fixture-user", "eventType": "document_created"}],
    }
    s3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
    clients = {"sqs": sqs, "s3": s3}
    monkeypatch.setattr(analytics_daily.boto3, "client", lambda service, **kwargs: clients[service])
    monkeypatch.setattr(analytics_daily.boto3, "resource", Mock(return_value=dynamodb))
    monkeypatch.setattr(analytics_daily.psycopg2, "connect", Mock())

    with Stubber(s3) as stub, patch.object(s3, "put_object", wraps=s3.put_object) as putObject:
        stub.add_response("put_object", {})
        stub.add_response("put_object", {})
        stub.add_response("put_object", {}, {
            "Bucket": BUCKET,
            "Key": ANY,
            "Body": ANY,
            "ExpectedBucketOwner": BUCKET_OWNER,
        })
        stub.add_response("put_object", {})
        analytics_daily.main()
        stub.assert_no_pending_responses()

    assert putObject.call_args_list[2].kwargs["Key"].endswith("/top_users.jsonl.gz")
