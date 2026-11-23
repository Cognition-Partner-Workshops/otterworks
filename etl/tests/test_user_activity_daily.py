import configparser
import gzip
from datetime import UTC, datetime
from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock, patch

import boto3
from botocore.exceptions import ClientError
from botocore.stub import ANY, Stubber

from etl.scripts import user_activity_daily


class UserActivityDailyTest(TestCase):
    def setUp(self):
        self.owner = "000000000000"
        self.bucket = "test-data-lake"
        self.config = configparser.ConfigParser()
        self.config.read_dict({
            "aws": {"access_key": "test", "secret_key": "test", "region": "us-east-1"},
            "database": {
                "host": "localhost", "port": "5432", "database": "test",
                "user": "test", "password": "test",
            },
            "s3": {"data_lake_bucket": self.bucket, "data_lake_bucket_owner": self.owner},
        })
        connection = Mock()
        connection.cursor.return_value.fetchall.return_value = []

        now = datetime(2026, 1, 1, tzinfo=UTC)
        date = Mock(wraps=datetime)
        date.now.return_value = now
        reader = Mock()
        reader.get_object.side_effect = [
            {"Body": BytesIO(gzip.compress(b'{"user_id":"fixture-user","total":4}'))},
            *[ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")] * 29,
        ]
        uploader = boto3.client(
            "s3", region_name="us-east-1", aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        self.stubber = self.enterContext(Stubber(uploader))
        self.enterContext(patch.object(user_activity_daily, "configparser", Mock(
            ConfigParser=Mock(return_value=self.config),
        )))
        self.enterContext(patch.object(user_activity_daily, "datetime", date))
        self.enterContext(patch.object(user_activity_daily.psycopg2, "connect", return_value=connection))
        self.enterContext(patch.object(user_activity_daily.boto3, "client", side_effect=[reader, uploader]))

        # The sibling writes are outside this finding and retain their existing contract.
        for prefix in ("2026-01-01", "latest"):
            self.stubber.add_response("put_object", {}, {
                "Bucket": self.bucket,
                "Key": f"reports/user-activity/{prefix}/activity_report.json",
                "Body": ANY,
            })
        self.summary_request = {
            "Bucket": self.bucket,
            "Key": "reports/user-activity/2026-01-01/user_summaries.jsonl",
            "Body": b'{"user_id": "fixture-user", "total_actions": 4, "active_days": 1, "actions_by_type": {}}\n',
            "ExpectedBucketOwner": self.owner,
        }

    def test_user_summaries_upload_uses_the_configured_bucket_owner(self):
        self.stubber.add_response("put_object", {}, self.summary_request)
        user_activity_daily.main()
        self.stubber.assert_no_pending_responses()

    def test_user_summaries_upload_propagates_s3_owner_rejection(self):
        self.stubber.add_client_error(
            "put_object", "AccessDenied", http_status_code=403, expected_params=self.summary_request,
        )
        with self.assertRaisesRegex(ClientError, "AccessDenied"):
            user_activity_daily.main()
        self.stubber.assert_no_pending_responses()

    def test_user_summaries_upload_requires_a_valid_configured_owner(self):
        self.config["s3"]["data_lake_bucket_owner"] = ""
        with self.assertRaisesRegex(ValueError, "12-digit AWS account ID"):
            user_activity_daily.main()
        self.stubber.assert_no_pending_responses()
