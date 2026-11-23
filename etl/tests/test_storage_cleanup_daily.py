import json
from configparser import ConfigParser
from datetime import datetime
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from etl.scripts import storage_cleanup_daily


@pytest.mark.parametrize("configuredOwner", [None, "111122223333"], ids=["caller", "configured"])
@pytest.mark.parametrize("deleteDenied", [False, True], ids=["allowed", "denied"])
def test_delete_checks_file_storage_bucket_owner(monkeypatch, configuredOwner, deleteDenied):
    config = ConfigParser()
    config.read_dict({
        "aws": {"access_key": "test", "secret_key": "test", "region": "us-east-1"},
        "s3": {
            "file_storage_bucket": "test-files",
            "quarantine_bucket": "test-quarantine",
            "data_lake_bucket": "test-reports",
        },
    })
    if configuredOwner:
        config.set("s3", "file_storage_bucket_owner", configuredOwner)
    monkeypatch.setattr(storage_cleanup_daily.configparser, "ConfigParser", lambda: config)
    monkeypatch.setattr(config, "read", Mock())

    orphan = "files/orphan"
    s3 = Mock()
    s3.get_paginator.return_value.paginate.return_value = [{"Contents": [{
        "Key": orphan, "Size": 4, "LastModified": datetime.fromisoformat("2026-08-05T00:00:00+00:00"),
    }]}]
    if deleteDenied:
        s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}, "ResponseMetadata": {"HTTPStatusCode": 403}},
            "DeleteObject",
        )

    sts = Mock()
    callerAccount = "444455556666"
    sts.get_caller_identity.return_value = {"Account": callerAccount}
    client = Mock(side_effect=lambda service, **_: {"s3": s3, "sts": sts}[service])
    dynamodb = Mock()
    dynamodb.Table.return_value.scan.return_value = {"Items": []}
    monkeypatch.setattr(storage_cleanup_daily.boto3, "client", client)
    monkeypatch.setattr(storage_cleanup_daily.boto3, "resource", Mock(return_value=dynamodb))

    storage_cleanup_daily.main()

    s3.delete_object.assert_called_once_with(
        Bucket="test-files", Key=orphan, ExpectedBucketOwner=configuredOwner or callerAccount,
    )
    if configuredOwner:
        sts.get_caller_identity.assert_not_called()
    else:
        sts.get_caller_identity.assert_called_once_with()
    report = json.loads(s3.put_object.call_args.kwargs["Body"])
    assert report["cleanup"]["objects_quarantined"] == int(not deleteDenied)
    assert report["cleanup"]["objects_failed"] == int(deleteDenied)
