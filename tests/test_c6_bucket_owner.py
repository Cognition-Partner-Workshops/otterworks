"""C6: every S3 object call in the ETL jobs pins the expected bucket owner."""
import ast
import pathlib
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "etl" / "scripts"
S3_OBJECT_CALLS = {"put_object", "get_object", "copy_object", "delete_object", "list_objects_v2"}


def _calls():
    for path in sorted(SCRIPTS.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in S3_OBJECT_CALLS:
                yield path.name, node


def test_every_s3_object_call_sets_expected_bucket_owner():
    calls = list(_calls())
    assert calls
    missing = [f"{name}:{node.lineno}" for name, node in calls
               if "ExpectedBucketOwner" not in {kw.arg for kw in node.keywords}]
    assert missing == []


def test_copy_object_also_pins_source_owner():
    for name, node in _calls():
        if node.func.attr == "copy_object":
            assert "ExpectedSourceBucketOwner" in {kw.arg for kw in node.keywords}, f"{name}:{node.lineno}"


@pytest.mark.parametrize("value", ["", "abc", "12345", "1234567890123"])
def test_expected_bucket_owner_rejects_invalid(monkeypatch, value):
    sys.path.insert(0, str(SCRIPTS))
    from bucket_owner import expected_bucket_owner
    monkeypatch.setenv("ETL_S3_BUCKET_OWNER", value)
    with pytest.raises(RuntimeError):
        expected_bucket_owner()


def test_expected_bucket_owner_accepts_account_id(monkeypatch):
    sys.path.insert(0, str(SCRIPTS))
    from bucket_owner import expected_bucket_owner
    monkeypatch.setenv("ETL_S3_BUCKET_OWNER", "123456789012")
    assert expected_bucket_owner() == "123456789012"


def _first_call_line(tree, attr):
    lines = [node.lineno for node in ast.walk(tree)
             if isinstance(node, ast.Call)
             and getattr(node.func, "attr", getattr(node.func, "id", None)) == attr]
    return min(lines) if lines else None


def test_owner_resolved_before_sqs_messages_are_consumed():
    for path in sorted(SCRIPTS.glob("*.py")):
        tree = ast.parse(path.read_text())
        consume = _first_call_line(tree, "receive_message")
        if consume is None:
            continue
        owner = _first_call_line(tree, "expected_bucket_owner")
        assert owner is not None and owner < consume, path.name


class _FakeS3:
    def __init__(self, code):
        self.code = code

    def get_object(self, **kwargs):
        from botocore.exceptions import ClientError
        raise ClientError({"Error": {"Code": self.code}}, "GetObject")


def test_activity_day_read_skips_only_missing_keys():
    sys.path.insert(0, str(SCRIPTS))
    from botocore.exceptions import ClientError
    from user_activity_daily import read_activity_day
    assert read_activity_day(_FakeS3("NoSuchKey"), "lake", "123456789012", "k") is None
    with pytest.raises(ClientError):
        read_activity_day(_FakeS3("AccessDenied"), "lake", "123456789012", "k")


def test_access_log_bucket_outputs_wait_for_delivery_policy():
    import re
    tf = (pathlib.Path(__file__).resolve().parents[1]
          / "infrastructure/terraform/modules/access-log-bucket/main.tf").read_text()
    for name in ("id", "arn"):
        block = re.search(r'output "%s" \{(.*?)\n\}' % name, tf, re.S).group(1)
        assert re.search(r"depends_on\s*=\s*\[aws_s3_bucket_policy\.this\]", block), name
