import gzip
import io
from datetime import datetime
from unittest.mock import Mock

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import ANY, Stubber

from etl.scripts import user_activity_daily

BUCKET = "otterworks-data-lake-fixture"
OWNER = "123456789012"
DATE = datetime.fromisoformat("2026-08-05T00:00:00+00:00")
REPORT = "reports/user-activity/2026-08-05/activity_report.json"


@pytest.fixture
def upload(monkeypatch):
    def readConfig(parser, path):
        assert path == "/opt/etl/config.ini"
        parser.read_dict({
            "aws": {"access_key": "test", "secret_key": "test", "region": "us-east-1"},
            "database": {
                "host": "unused", "port": "5432", "database": "test",
                "user": "test", "password": "test",
            },
            "s3": {"data_lake_bucket": BUCKET},
        })

    monkeypatch.setattr(user_activity_daily.configparser.ConfigParser, "read", readConfig)
    monkeypatch.setenv("ETL_DATA_LAKE_BUCKET_OWNER", OWNER)
    clock = Mock(wraps=datetime)
    clock.now.return_value = DATE
    monkeypatch.setattr(user_activity_daily, "datetime", clock)
    connect = Mock()
    connect.return_value.cursor.return_value.fetchall.return_value = []
    monkeypatch.setattr(user_activity_daily.psycopg2, "connect", connect)

    reader = Mock()
    reader.get_object.side_effect = [
        {"Body": io.BytesIO(gzip.compress(b'{"user_id":"fixture","total":3}\n'))},
        *[FileNotFoundError] * 29,
    ]
    writer = boto3.client(
        "s3", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test",
    )
    monkeypatch.setattr(user_activity_daily.boto3, "client", Mock(side_effect=[reader, writer]))
    with Stubber(writer) as stub:
        yield stub


def test_main_checks_the_owner_on_the_daily_report_upload(upload):
    upload.add_response("put_object", {}, {
        "Bucket": BUCKET, "Key": REPORT, "Body": ANY, "ExpectedBucketOwner": OWNER,
    })
    upload.add_response("put_object", {})
    upload.add_response("put_object", {})

    user_activity_daily.main()
    upload.assert_no_pending_responses()


def test_main_aborts_the_report_on_s3_owner_denial(upload):
    upload.add_client_error(
        "put_object", service_error_code="AccessDenied", http_status_code=403,
        expected_params={"Bucket": BUCKET, "Key": REPORT, "Body": ANY, "ExpectedBucketOwner": OWNER},
    )

    with pytest.raises(ClientError) as error:
        user_activity_daily.main()

    assert error.value.response["ResponseMetadata"]["HTTPStatusCode"] == 403
    assert error.value.response["Error"]["Code"] == "AccessDenied"
    upload.assert_no_pending_responses()


@pytest.mark.parametrize("owner", [None, "", "12345", "１２３４５６７８９０１２"])
def test_main_rejects_invalid_owner_configuration(upload, monkeypatch, owner):
    if owner is None:
        monkeypatch.delenv("ETL_DATA_LAKE_BUCKET_OWNER")
    else:
        monkeypatch.setenv("ETL_DATA_LAKE_BUCKET_OWNER", owner)

    with pytest.raises(ValueError, match="ETL_DATA_LAKE_BUCKET_OWNER"):
        user_activity_daily.main()

    user_activity_daily.psycopg2.connect.assert_not_called()
    user_activity_daily.boto3.client.assert_not_called()
