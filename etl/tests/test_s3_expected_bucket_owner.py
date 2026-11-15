"""Every boto3 S3 call in etl/scripts/ must verify bucket ownership (SonarCloud python:S7608).

The ETL scripts are monolithic cron jobs with no injectable dependencies, so this test inspects
their source: each S3 data-plane call has to pass ExpectedBucketOwner, and the value has to come
from the [s3] bucket_owner_account_id setting in etl/config.ini.
"""
import ast
import configparser
import pathlib

import pytest

etlDir = pathlib.Path(__file__).resolve().parents[1]
scriptPaths = sorted((etlDir / "scripts").glob("*.py"))

s3Operations = {
    "put_object",
    "get_object",
    "copy_object",
    "delete_object",
    "delete_objects",
    "head_object",
    "list_objects",
    "list_objects_v2",
    "paginate",
}


def keywordNames(call):
    return {kw.arg for kw in call.keywords}


def s3Calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in s3Operations:
                yield node


def test_config_declares_bucket_owner_account_id():
    config = configparser.ConfigParser()
    config.read(etlDir / "config.ini")
    accountId = config.get("s3", "bucket_owner_account_id")
    assert accountId.isdigit() and len(accountId) == 12


@pytest.mark.parametrize("scriptPath", scriptPaths, ids=lambda p: p.name)
def test_every_s3_call_passes_expected_bucket_owner(scriptPath):
    tree = ast.parse(scriptPath.read_text(), filename=str(scriptPath))
    calls = list(s3Calls(tree))
    missing = [
        "%s:%d %s()" % (scriptPath.name, call.lineno, call.func.attr)
        for call in calls
        if "ExpectedBucketOwner" not in keywordNames(call)
    ]
    assert not missing, "S3 calls without ExpectedBucketOwner: %s" % missing

    copyCalls = [c for c in calls if c.func.attr == "copy_object"]
    missingSource = [
        "%s:%d" % (scriptPath.name, c.lineno)
        for c in copyCalls
        if "ExpectedSourceBucketOwner" not in keywordNames(c)
    ]
    assert not missingSource, "copy_object without ExpectedSourceBucketOwner: %s" % missingSource

    if calls:
        source = scriptPath.read_text()
        assert 'config.get("s3", "bucket_owner_account_id")' in source, (
            "%s uses S3 but does not read bucket_owner_account_id from config.ini" % scriptPath.name
        )
