import configparser
import unittest
from unittest.mock import MagicMock, patch

import boto3
from botocore.stub import ANY, Stubber

from etl.scripts import audit_archive_weekly


class AuditArchiveReportOwnerTest(unittest.TestCase):
    def setUp(self):
        self.config = configparser.ConfigParser()
        self.config.read_dict({
            "aws": {"access_key": "test", "secret_key": "test", "region": "us-east-1"},
            "s3": {"archive_bucket": "otterworks-audit-archive", "archive_bucket_owner": "012345678901"},
        })

    def test_report_put_pins_bucket_owner(self):
        dynamodb = MagicMock()
        dynamodb.Table.return_value.scan.return_value = {
            "Items": [{"event_id": "test-event", "timestamp": "2020-01-01T00:00:00Z"}],
        }
        reportClient = boto3.client(
            "s3", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test",
        )
        with Stubber(reportClient) as reportStub:
            reportStub.add_response("put_object", {}, {
                "Bucket": "otterworks-audit-archive",
                "Key": ANY,
                "Body": ANY,
                "ExpectedBucketOwner": "012345678901",
            })
            with (
                patch.object(audit_archive_weekly.configparser, "ConfigParser", return_value=self.config),
                patch.object(audit_archive_weekly.boto3, "resource", return_value=dynamodb),
                patch.object(audit_archive_weekly.boto3, "client", side_effect=[MagicMock(), reportClient]),
            ):
                audit_archive_weekly.main()
            reportStub.assert_no_pending_responses()

    def test_missing_or_invalid_owner_fails_before_aws_calls(self):
        for owner in (None, "", "not-an-account"):
            with self.subTest(owner=owner):
                if owner is None:
                    self.config.remove_option("s3", "archive_bucket_owner")
                else:
                    self.config.set("s3", "archive_bucket_owner", owner)
                with (
                    patch.object(audit_archive_weekly.configparser, "ConfigParser", return_value=self.config),
                    patch.object(audit_archive_weekly.boto3, "resource") as resource,
                    patch.object(audit_archive_weekly.boto3, "client") as client,
                    self.assertRaisesRegex(ValueError, "archive_bucket_owner"),
                ):
                    audit_archive_weekly.main()
                resource.assert_not_called()
                client.assert_not_called()
