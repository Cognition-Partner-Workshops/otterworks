import configparser
from datetime import datetime
from unittest.mock import Mock

import boto3
import pytest
from botocore.stub import ANY, Stubber

from etl.scripts import analytics_daily


@pytest.fixture
def batchConfig(tmp_path, monkeypatch):
    configPath = tmp_path / "config.ini"
    configPath.write_text(
        "[aws]\naccess_key = test\nsecret_key = test\nregion = us-east-1\n"
        "[database]\nhost = localhost\nport = 5432\ndatabase = test\nuser = test\npassword = test\n"
        "[s3]\ndata_lake_bucket = analytics-test\nanalytics_prefix = analytics/daily\n",
        encoding="utf-8",
    )
    readConfig = configparser.ConfigParser.read
    monkeypatch.setattr(configparser.ConfigParser, "read", lambda self, _: readConfig(self, configPath))
    return configPath


def test_daily_report_upload_pins_configured_bucket_owner(batchConfig, monkeypatch):
    expectedOwner = "012345678901"
    with batchConfig.open("a", encoding="utf-8") as configFile:
        configFile.write(f"expected_bucket_owner = {expectedOwner}\n")

    reportClient = boto3.client(
        "s3", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
    )
    sqsClient = Mock()
    sqsClient.receive_message.return_value = {"Messages": []}
    aggregateClient = Mock()
    clients = Mock(side_effect=[sqsClient, aggregateClient, reportClient])
    monkeypatch.setattr(analytics_daily.boto3, "client", clients)
    dynamodb = Mock()
    dynamodb.Table.return_value.scan.return_value = {
        "Items": [{"eventType": "document_created", "userId": "fixture-user"}]
    }
    monkeypatch.setattr(analytics_daily.boto3, "resource", Mock(return_value=dynamodb))
    monkeypatch.setattr(analytics_daily.psycopg2, "connect", Mock())

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromisoformat("2026-08-05T00:00:00+00:00").astimezone(tz)

    monkeypatch.setattr(analytics_daily, "datetime", FixedDateTime)

    with Stubber(reportClient) as stubber:
        stubber.add_response(
            "put_object",
            {},
            {
                "Bucket": "analytics-test",
                "Key": "reports/analytics/daily/2026-08-05/report.json",
                "Body": ANY,
                "ExpectedBucketOwner": expectedOwner,
            },
        )
        analytics_daily.main()
        stubber.assert_no_pending_responses()


@pytest.mark.parametrize("configValue", ["", "expected_bucket_owner =\n", "expected_bucket_owner = invalid\n"])
def test_invalid_or_missing_bucket_owner_stops_before_aws_calls(batchConfig, monkeypatch, configValue):
    with batchConfig.open("a", encoding="utf-8") as configFile:
        configFile.write(configValue)
    clients = Mock()
    monkeypatch.setattr(analytics_daily.boto3, "client", clients)

    with pytest.raises(ValueError, match=r"expected_bucket_owner.*12-digit"):
        analytics_daily.main()

    clients.assert_not_called()
