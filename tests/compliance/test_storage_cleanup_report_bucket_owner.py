import json
import runpy
import sys
from configparser import ConfigParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "etl/scripts/storage_cleanup_daily.py"
EXPECTED_OWNER = "012345678901"
REPORT_BUCKET = "storage-cleanup-reports-test"


@pytest.fixture
def storage_cleanup(monkeypatch):
    config = ConfigParser()
    config.read_dict({
        "aws": {"access_key": "test", "secret_key": "test", "region": "us-east-1"},
        "s3": {
            "file_storage_bucket": "files-test",
            "quarantine_bucket": "quarantine-test",
            "data_lake_bucket": REPORT_BUCKET,
            "bucket_owner_account_id": EXPECTED_OWNER,
        },
    })
    monkeypatch.setattr(ConfigParser, "read", lambda parser, _: parser.read_dict(config))

    inventory = Mock()
    inventory.get_paginator.return_value.paginate.return_value = [{}]
    report = Mock()
    boto = SimpleNamespace(client=Mock(side_effect=[inventory, report]), resource=Mock())
    boto.resource.return_value.Table.return_value.scan.return_value = {"Items": []}
    monkeypatch.setitem(sys.modules, "boto3", boto)
    return runpy.run_path(str(SCRIPT))["main"], config, boto, report


def test_storage_cleanup_pins_the_report_bucket_owner(storage_cleanup):
    main, _, _, report = storage_cleanup
    main()

    report.put_object.assert_called_once()
    request = report.put_object.call_args.kwargs
    assert request["Bucket"] == REPORT_BUCKET
    assert request.get("ExpectedBucketOwner") == EXPECTED_OWNER
    payload = json.loads(request["Body"])
    assert payload["report_type"] == "storage_cleanup"
    assert request["Key"] == f"reports/storage-cleanup/{payload['report_date']}/report.json"
    assert payload["cleanup"]["objects_quarantined"] == 0


def test_storage_cleanup_does_not_retry_without_owner_on_denial(storage_cleanup):
    main, _, _, report = storage_cleanup
    report.put_object.side_effect = PermissionError("simulated S3 owner mismatch (403)")

    with pytest.raises(PermissionError, match="simulated S3 owner mismatch"):
        main()

    report.put_object.assert_called_once()
    assert report.put_object.call_args.kwargs.get("ExpectedBucketOwner") == EXPECTED_OWNER


@pytest.mark.parametrize("invalid_owner", [None, "", "not-an-account"])
def test_storage_cleanup_rejects_missing_or_invalid_owner_before_aws(storage_cleanup, invalid_owner):
    main, config, boto, _ = storage_cleanup
    if invalid_owner is None:
        config.remove_option("s3", "bucket_owner_account_id")
    else:
        config.set("s3", "bucket_owner_account_id", invalid_owner)

    with pytest.raises(ValueError, match="bucket_owner_account_id"):
        main()

    boto.client.assert_not_called()
    boto.resource.assert_not_called()
