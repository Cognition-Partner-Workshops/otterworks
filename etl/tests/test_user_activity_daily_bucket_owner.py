import configparser
import gzip
import io
import json
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from botocore.serialize import create_serializer
from botocore.session import get_session

from etl.scripts import user_activity_daily


@pytest.fixture
def job(monkeypatch):
    config = configparser.ConfigParser()
    config.read_dict({
        "aws": {"access_key": "test", "secret_key": "test", "region": "us-east-1"},
        "database": {
            "host": "localhost", "port": "5432", "database": "fixture",
            "user": "test", "password": "test",
        },
        "s3": {"data_lake_bucket": "fixture-data-lake"},
    })
    database = Mock()
    database.cursor.return_value.fetchall.return_value = []
    s3 = Mock()
    model = get_session().get_service_model("s3").operation_model("GetObject")
    serializer = create_serializer(model.metadata["protocol"])
    headers = []

    def get_object(**params):
        headers.append(serializer.serialize_to_request(params, model)["headers"])
        if len(headers) > 1:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        payload = b'{"user_id":"fixture-user","total":4,"actions":{"edit":4}}\n'
        return {"Body": io.BytesIO(gzip.compress(payload))}

    s3.get_object.side_effect = get_object
    monkeypatch.setattr(user_activity_daily.configparser, "ConfigParser", lambda: config)
    monkeypatch.setattr(config, "read", Mock())
    monkeypatch.setattr(user_activity_daily.psycopg2, "connect", Mock(return_value=database))
    monkeypatch.setattr(user_activity_daily.boto3, "client", Mock(return_value=s3))
    return config, s3, headers


def test_read_sends_expected_owner_and_aggregates_activity(job):
    config, s3, headers = job
    config.set("s3", "data_lake_bucket_owner", "000000000000")

    user_activity_daily.main()

    assert len(headers) == 30
    assert all(header.get("x-amz-expected-bucket-owner") == "000000000000" for header in headers)
    report = json.loads(s3.put_object.call_args_list[0].kwargs["Body"])
    assert report["top_users"] == [{
        "user_id": "fixture-user", "total_actions": 4,
        "active_days": 1, "actions_by_type": {"edit": 4},
    }]


@pytest.mark.parametrize("owner", [None, "", "bad-owner"])
def test_missing_or_invalid_owner_skips_reads_and_logs(job, owner, capsys):
    config, s3, _ = job
    if owner is not None:
        config.set("s3", "data_lake_bucket_owner", owner)

    user_activity_daily.main()

    s3.get_object.assert_not_called()
    assert "Skipping per-user S3 reads" in capsys.readouterr().out
    report = json.loads(s3.put_object.call_args_list[0].kwargs["Body"])
    assert report["top_users"] == []
