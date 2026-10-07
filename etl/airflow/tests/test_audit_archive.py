from __future__ import annotations

import gzip
import io
import json
from decimal import Decimal

import pytest

from otterworks_etl.audit_archive import (
    ArchiveMismatchError,
    ArchiveOverwriteError,
    archive_key,
    build_report,
    check_key_schema,
    check_overwrite,
    compress_lines,
    cutoff_date,
    decompress_lines,
    delete_in_batches,
    delete_plan,
    encode_events,
    read_object,
    scan_events,
    sha256_hex,
    verified_delete_plan,
)
from tests.audit_fakes import FakeS3Client, FakeTable

BUCKET = "otterworks-audit-archive"


def _item(i, ts="2025-09-01T00:00:00Z", **extra):
    return {"id": "a-%03d" % i, "event_id": "a-%03d" % i, "timestamp": ts, **extra}


def test_cutoff_is_the_legacy_string():
    assert cutoff_date("2026-03-15", 90) == "2025-12-15T00:00:00Z"
    assert cutoff_date("2026-03-15", 7) == "2026-03-08T00:00:00Z"


def test_scan_follows_last_evaluated_key_with_the_string_filter():
    items = [_item(i) for i in range(23)] + [
        _item(100, "2025-12-15T00:00:00Z"),  # exactly on the cutoff: kept
        _item(101, "2025-12-15T00:00:00.000Z"),  # same instant, sorts before: archived
        _item(102, "2026-03-01T00:00:00Z"),
        {"id": "num", "timestamp": Decimal(1700000000)},  # numeric: never matched
    ]
    events = scan_events(FakeTable(items, page_size=5), "2025-12-15T00:00:00Z")
    assert [e["id"] for e in events] == ["a-%03d" % i for i in range(23)] + ["a-101"]


def test_decimals_encode_as_legacy():
    event = {
        "id": "d",
        "n": Decimal("100.0"),
        "big": Decimal("12345678901234567890123456789012345678"),
        "neg_zero": Decimal("-0.0"),
        "f": Decimal("1.1"),
        "tiny": Decimal("1e-10"),
        "nested": {"m": [Decimal("19.99"), Decimal("2")]},
    }
    (line,) = encode_events([event])
    assert line == (
        '{"id": "d", "n": 100, "big": 12345678901234567890123456789012345678, "neg_zero": 0, '
        '"f": 1.1, "tiny": 1e-10, "nested": {"m": [19.99, 2]}}'
    )


def test_archive_layout_and_deterministic_gzip():
    lines = ['{"id": "a"}', '{"id": "b"}']
    body = compress_lines(lines)
    assert gzip.decompress(body) == b'{"id": "a"}\n{"id": "b"}\n'
    assert compress_lines(lines) == body
    legacy = io.BytesIO()
    with gzip.GzipFile(fileobj=legacy, mode="wb") as gz:
        for line in lines:
            gz.write(line.encode("utf-8"))
            gz.write(b"\n")
    assert len(legacy.getvalue()) == len(body)
    assert decompress_lines(body) == lines
    assert (
        archive_key("audit-archive", "2026-03-15")
        == "audit-archive/year=2026/week=2026-03-15/audit_events.jsonl.gz"
    )


def test_read_object_restores_glacier_and_waits():
    s3 = FakeS3Client(restore_polls=3)
    s3.put(BUCKET, "k", b"body", "GLACIER")
    sleeps = []
    assert read_object(s3, BUCKET, "k", sleep=sleeps.append) == b"body"
    assert s3.restores == ["k"] and len(sleeps) == 2


def test_read_object_times_out_while_restoring():
    s3 = FakeS3Client(restore_polls=10**6)
    s3.put(BUCKET, "k", b"body", "GLACIER")
    now = iter(range(0, 10**6, 100))
    with pytest.raises(TimeoutError):
        read_object(s3, BUCKET, "k", timeout=250, sleep=lambda s: None, clock=lambda: next(now))


def test_delete_plan_keys_on_id_and_counts_items_without_id():
    lines = encode_events(
        [_item(1), {"event_id": "no-id", "timestamp": "2025-01-01T00:00:00Z"}, _item(2), _item(1)]
    )
    plan = delete_plan(lines)
    assert plan.keys == ({"id": "a-001"}, {"id": "a-002"})
    assert plan.skipped_without_id == 1


def test_delete_plan_keeps_archived_events_not_provably_before_the_cutoff():
    cutoff = "2025-12-15T00:00:00Z"
    stamps = {
        "before-1s": "2025-12-14T23:59:59Z",
        "plus-offset-before": "2025-12-14T23:00:00+00:00",
        "millis-same-instant": "2025-12-15T00:00:00.000Z",
        "plus-offset-same-instant": "2025-12-15T00:00:00+00:00",
        "date-only-same-day": "2025-12-15",
        "minus5-after": "2025-12-14T23:00:00-05:00",
        "garbage": "2025-12-1",
    }
    lines = encode_events({"id": k, "timestamp": v} for k, v in stamps.items())
    plan = delete_plan(lines, cutoff)
    assert plan.keys == ({"id": "before-1s"}, {"id": "plus-offset-before"})
    assert plan.kept_within_retention == 5
    assert delete_plan(lines).kept_within_retention == 0


def test_verified_plan_refuses_an_archive_that_is_not_the_upload():
    s3 = FakeS3Client()
    body = compress_lines(encode_events([_item(1)]))
    s3.put(BUCKET, "k", compress_lines(encode_events([_item(1), _item(2)])), "GLACIER")
    with pytest.raises(ArchiveMismatchError):
        verified_delete_plan(s3, BUCKET, "k", sha256_hex(body), sleep=lambda s: None)
    s3.put(BUCKET, "k", body, "GLACIER")
    plan = verified_delete_plan(s3, BUCKET, "k", sha256_hex(body), sleep=lambda s: None)
    assert plan.keys == ({"id": "a-001"},)


def test_overwrite_only_when_nothing_archived_is_dropped():
    check_overwrite(["a", "b"], ["a", "b", "c"])
    with pytest.raises(ArchiveOverwriteError):
        check_overwrite(["a", "b"], ["b"])


def test_key_schema_must_be_id_only():
    check_key_schema(FakeTable([]))
    composite = [
        {"AttributeName": "event_id", "KeyType": "HASH"},
        {"AttributeName": "timestamp", "KeyType": "RANGE"},
    ]
    with pytest.raises(ValueError):
        check_key_schema(FakeTable([], key_schema=composite))


def test_deletes_in_batches_of_25():
    table = FakeTable([_item(i) for i in range(60)])
    keys = [{"id": "a-%03d" % i} for i in range(60)]
    assert delete_in_batches(table, keys, 25) == 60
    assert table.batches == [25, 25, 10] and table.items == []
    with pytest.raises(ValueError):
        delete_in_batches(table, keys, 26)


def test_report_is_the_legacy_contract():
    report = build_report(
        ds="2026-03-15",
        generated_at="t",
        retention_days=90,
        cutoff="2025-12-15T00:00:00Z",
        events_archived=2,
        events_deleted=0,
        bucket=BUCKET,
        key="audit-archive/x.jsonl.gz",
        storage_class="GLACIER",
        compressed_size=182,
    )
    assert json.loads(json.dumps(report)) == {
        "report_type": "audit_archive_compliance",
        "execution_date": "2026-03-15",
        "generated_at": "t",
        "retention_policy": {"retention_days": 90, "cutoff_date": "2025-12-15T00:00:00Z"},
        "results": {
            "events_scanned": 2,
            "events_archived": 2,
            "events_deleted_from_source": 0,
            "archive_location": f"s3://{BUCKET}/audit-archive/x.jsonl.gz",
            "archive_storage_class": "GLACIER",
            "compressed_size_bytes": 182,
        },
        "compliance": {
            "gdpr_compliant": True,
            "soc2_compliant": True,
            "data_encrypted_at_rest": True,
            "data_encrypted_in_transit": True,
        },
    }
