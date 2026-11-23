import configparser
from datetime import datetime, timezone
from unittest import mock

import pytest
from botocore.exceptions import ClientError

ACCOUNT_ID = "123456789012"
CONFIG = """
[aws]
access_key = test
secret_key = test
region = us-east-1

[s3]
file_storage_bucket = files-bucket
quarantine_bucket = quarantine-bucket
data_lake_bucket = data-lake-bucket
"""


@pytest.fixture
def clients(monkeypatch, load_script):
    module = load_script("storage_cleanup_daily")

    class FixtureConfig(configparser.ConfigParser):
        def read(self, filenames, encoding=None):
            self.read_string(CONFIG)
            return [filenames]

    monkeypatch.setattr(module.configparser, "ConfigParser", FixtureConfig)

    s3 = mock.MagicMock(name="s3")
    s3.get_paginator.return_value.paginate.return_value = [{
        "Contents": [
            {"Key": "files/u1/kept", "Size": 10, "LastModified": datetime.now(tz=timezone.utc)},
            {"Key": "files/u1/orphan", "Size": 20, "LastModified": datetime.now(tz=timezone.utc)},
        ]
    }]
    sts = mock.MagicMock(name="sts")
    sts.get_caller_identity.return_value = {"Account": ACCOUNT_ID}
    dynamodb = mock.MagicMock(name="dynamodb")
    dynamodb.Table.return_value.scan.return_value = {"Items": [{"s3_key": "files/u1/kept"}]}

    monkeypatch.setattr(module.boto3, "client", lambda service, **_: {"s3": s3, "sts": sts}[service])
    monkeypatch.setattr(module.boto3, "resource", lambda service, **_: dynamodb)
    return module, s3


def test_quarantine_copy_verifies_both_bucket_owners(clients):
    module, s3 = clients

    module.main()

    s3.copy_object.assert_called_once()
    kwargs = s3.copy_object.call_args.kwargs
    assert kwargs["Bucket"] == "quarantine-bucket"
    assert kwargs["CopySource"] == {"Bucket": "files-bucket", "Key": "files/u1/orphan"}
    assert kwargs["ExpectedBucketOwner"] == ACCOUNT_ID
    assert kwargs["ExpectedSourceBucketOwner"] == ACCOUNT_ID


def test_rejected_copy_leaves_the_original_in_place(clients):
    module, s3 = clients
    s3.copy_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "CopyObject"
    )

    module.main()

    s3.delete_object.assert_not_called()
    report = s3.put_object.call_args.kwargs["Body"].decode("utf-8")
    assert '"objects_quarantined": 0' in report
    assert '"objects_failed": 1' in report
