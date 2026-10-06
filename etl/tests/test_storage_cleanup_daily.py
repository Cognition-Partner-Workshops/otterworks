import boto3
import pytest

from conftest import load_script

FILES = "otterworks-file-storage"
QUARANTINE = "otterworks-file-quarantine"
DATA_LAKE = "otterworks-data-lake"
TABLE_NAME = "otterworks-file-metadata"


def _setup(objects, referenced):
    s3 = boto3.client("s3", region_name="us-east-1")
    for bucket in (FILES, QUARANTINE, DATA_LAKE):
        s3.create_bucket(Bucket=bucket)
    for key in objects:
        s3.put_object(Bucket=FILES, Key=key, Body=b"data")
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    for i, key in enumerate(referenced):
        dynamodb.put_item(TableName=TABLE_NAME, Item={"id": {"S": "f%d" % i}, "s3_key": {"S": key}})
    return s3


def _keys(s3, bucket, prefix=""):
    return sorted(o["Key"] for o in s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", []))


def test_empty_metadata_scan_does_not_quarantine_every_file(aws, etl_config):
    s3 = _setup(["files/u1/a", "files/u1/b"], referenced=[])
    etl_config.set("s3", "orphan_min_age_hours", 0)

    with pytest.raises(SystemExit) as exc:
        load_script("storage_cleanup_daily").main()

    assert exc.value.code == 1
    assert _keys(s3, FILES) == ["files/u1/a", "files/u1/b"]
    assert _keys(s3, QUARANTINE) == []


def test_recent_unreferenced_upload_is_not_quarantined(aws, etl_config):
    s3 = _setup(["files/u1/a", "files/u1/in-flight"], referenced=["files/u1/a"])

    load_script("storage_cleanup_daily").main()

    assert _keys(s3, FILES) == ["files/u1/a", "files/u1/in-flight"]
    assert _keys(s3, QUARANTINE) == []


def test_old_orphan_is_quarantined(aws, etl_config):
    s3 = _setup(["files/u1/a", "files/u1/orphan"], referenced=["files/u1/a"])
    etl_config.set("s3", "orphan_min_age_hours", 0)

    load_script("storage_cleanup_daily").main()

    assert _keys(s3, FILES) == ["files/u1/a"]
    assert [k.rsplit("/", 3)[-3:] for k in _keys(s3, QUARANTINE)] == [["files", "u1", "orphan"]]
