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
