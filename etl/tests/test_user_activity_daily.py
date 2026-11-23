import configparser
import importlib.util
import pathlib
from unittest import mock

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "user_activity_daily.py"
LATEST_KEY = "reports/user-activity/latest/activity_report.json"

CONFIG = """
[aws]
access_key = test
secret_key = test
region = us-east-1

[database]
host = localhost
port = 5432
database = otterworks_analytics
user = etl_user
password = etl

[s3]
data_lake_bucket = otterworks-data-lake
%s
"""


def load_script():
    spec = importlib.util.spec_from_file_location("user_activity_daily", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_main(s3_extra):
    module = load_script()
    s3Client = mock.MagicMock()
    s3Client.get_object.side_effect = Exception("NoSuchKey")
    cursor = mock.MagicMock()
    cursor.fetchall.return_value = []
    conn = mock.MagicMock()
    conn.cursor.return_value = cursor

    def read_config(self, *_args, **_kwargs):
        self.read_string(CONFIG % s3_extra)
        return []

    with mock.patch.object(configparser.ConfigParser, "read", read_config), \
            mock.patch.object(module.psycopg2, "connect", return_value=conn), \
            mock.patch.object(module.boto3, "client", return_value=s3Client):
        module.main()
    return s3Client


def latest_put(s3Client):
    calls = [c for c in s3Client.put_object.call_args_list if c.kwargs.get("Key") == LATEST_KEY]
    assert len(calls) == 1
    return calls[0].kwargs


def test_latest_report_put_verifies_bucket_owner():
    s3Client = run_main("expected_bucket_owner = 111122223333")
    kwargs = latest_put(s3Client)
    assert kwargs["Bucket"] == "otterworks-data-lake"
    assert kwargs["ExpectedBucketOwner"] == "111122223333"


def test_missing_expected_bucket_owner_fails_before_any_upload():
    with pytest.raises(configparser.NoOptionError):
        run_main("")
