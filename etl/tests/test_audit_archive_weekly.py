import configparser
import importlib.util
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "audit_archive_weekly.py"


def load_script():
    spec = importlib.util.spec_from_file_location("audit_archive_weekly", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTable:
    def __init__(self):
        self.deleted_keys = []

    def scan(self, **kwargs):
        return {
            "Items": [
                {
                    "event_id": "event-1",
                    "timestamp": "2020-01-01T00:00:00Z",
                }
            ]
        }

    def batch_writer(self):
        table = self

        class BatchWriter:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def delete_item(self, Key):
                table.deleted_keys.append(Key)

        return BatchWriter()


class FakeS3Client:
    def __init__(self):
        self.put_calls = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)


@pytest.mark.parametrize("configured_owner", ["111111111111", ""])
@pytest.mark.parametrize("upload_denied", [False, True])
def test_archive_upload_verifies_bucket_owner(monkeypatch, configured_owner, upload_denied):
    config = configparser.ConfigParser()
    config["aws"] = {
        "access_key": "000000000000",
        "secret_key": "test",
        "region": "us-east-1",
    }
    config["s3"] = {
        "archive_bucket": "audit-archive",
        "expected_bucket_owner": configured_owner,
    }
    monkeypatch.setattr(config, "read", lambda path: [])
    monkeypatch.setattr(configparser, "ConfigParser", lambda: config)

    module = load_script()
    table = FakeTable()
    s3_client = FakeS3Client()
    original_put = s3_client.put_object
    expected_owner = configured_owner or "000000000000"

    def put_object(**kwargs):
        original_put(**kwargs)
        if upload_denied:
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")

    monkeypatch.setattr(s3_client, "put_object", put_object)

    class FakeDynamoResource:
        def Table(self, name):
            assert name == "otterworks-audit-events"
            return table

    def fake_client(service_name, **kwargs):
        if service_name == "s3":
            return s3_client
        if service_name == "sts" and not configured_owner:
            assert kwargs["aws_access_key_id"] == "000000000000"

            class FakeStsClient:
                def get_caller_identity(self):
                    return {"Account": "000000000000"}

            return FakeStsClient()
        raise AssertionError(f"unexpected boto3 client: {service_name}")

    monkeypatch.setattr(module.boto3, "resource", lambda *args, **kwargs: FakeDynamoResource())
    monkeypatch.setattr(module.boto3, "client", fake_client)

    if upload_denied:
        with pytest.raises(ClientError, match="AccessDenied"):
            module.main()
        assert table.deleted_keys == []
        assert len(s3_client.put_calls) == 1
    else:
        module.main()
        assert table.deleted_keys == [{"event_id": "event-1", "timestamp": "2020-01-01T00:00:00Z"}]

    assert s3_client.put_calls[0]["ExpectedBucketOwner"] == expected_owner
