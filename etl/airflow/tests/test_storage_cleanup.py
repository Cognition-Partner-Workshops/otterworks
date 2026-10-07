from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from otterworks_etl.storage_cleanup import (
    build_report,
    find_orphans,
    normalize_reference,
    object_record,
    quarantine_key,
    quarantine_orphans,
    referenced_keys,
    scan_references,
)
from tests.storage_fakes import FakeS3, FakeTable

FILES = "otterworks-file-storage"
QUARANTINE = "otterworks-file-quarantine"


def _obj(key, size=1):
    return {"key": key, "size": size, "last_modified": "2026-06-01T01:00:00+00:00"}


# Shapes from the reference_mismatches golden.
OBJECTS = [
    _obj("files/", 0),
    _obj("files/user-alice/Report.PDF", 14),
    _obj("files/user-bob/leading.txt", 31),
    _obj("files/user-carol/uri.txt", 26),
    _obj("files/user-dan/shared.txt", 31),
]
REFERENCES = [
    "files/user-alice/report.pdf",
    "/files/user-bob/leading.txt",
    "s3://otterworks-file-storage/files/user-carol/uri.txt",
    "files/user-dan/shared.txt",
]


def _keys(result):
    return [o["key"] for o in result.orphans]


def test_object_record_keeps_key_size_and_iso_last_modified():
    stamp = datetime(2026, 6, 1, 2, 0, tzinfo=UTC)
    assert object_record({"Key": "files/a", "Size": 3, "LastModified": stamp, "ETag": "x"}) == {
        "key": "files/a",
        "size": 3,
        "last_modified": "2026-06-01T02:00:00+00:00",
    }


def test_referenced_keys_drops_missing_empty_and_non_string_and_dedups():
    values = ["files/b", "", "files/a", "files/b", Decimal(42), None]
    assert referenced_keys(values) == ["files/a", "files/b"]


def test_scan_references_follows_pagination_with_projection():
    items = [{"id": i, "s3_key": "files/%d" % i} for i in range(7)] + [{"id": "none"}]
    table = FakeTable(items, page_size=3)
    assert scan_references(table) == ["files/%d" % i for i in range(7)] + [""]
    assert table.scans == [None, {"_pos": 3}, {"_pos": 6}]


def test_exact_matching_is_legacy_and_counts_what_normalization_would_match():
    result = find_orphans(OBJECTS, REFERENCES, normalize=False, file_storage_bucket=FILES)
    assert _keys(result) == [
        "files/",
        "files/user-alice/Report.PDF",
        "files/user-bob/leading.txt",
        "files/user-carol/uri.txt",
    ]
    assert result.orphaned_bytes == 0 + 14 + 31 + 26
    assert result.normalizable_references == 2


def test_normalized_matching_keeps_slash_and_uri_references_but_never_folds_case():
    result = find_orphans(OBJECTS, REFERENCES, normalize=True, file_storage_bucket=FILES)
    assert _keys(result) == ["files/", "files/user-alice/Report.PDF"]
    assert result.orphaned_bytes == 14
    assert result.normalizable_references == 2


def test_normalization_only_strips_the_file_storage_bucket_uri():
    objects = [_obj("files/x.txt")]
    other = ["s3://some-other-bucket/files/x.txt"]
    assert _keys(find_orphans(objects, other, normalize=True, file_storage_bucket=FILES)) == [
        "files/x.txt"
    ]


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("/files/a.txt", "files/a.txt"),
        ("s3://otterworks-file-storage/files/a.txt", "files/a.txt"),
        ("s3://other/files/a.txt", "s3://other/files/a.txt"),
        ("files/A.txt", "files/A.txt"),
        ("files/a.txt", "files/a.txt"),
    ],
)
def test_normalize_reference(reference, expected):
    assert normalize_reference(reference, FILES) == expected


def test_orphans_keep_listing_order_and_duplicates_do_not_matter():
    objects = [_obj("files/c"), _obj("files/a"), _obj("files/b")]
    result = find_orphans(
        objects, ["files/a", "files/a"], normalize=False, file_storage_bucket=FILES
    )
    assert _keys(result) == ["files/c", "files/b"]


def test_quarantine_key_is_legacy_layout():
    assert quarantine_key("quarantined", "2026-06-01", "files/a b&+.txt") == (
        "quarantined/2026-06-01/files/a b&+.txt"
    )


def _s3_with(*keys):
    s3 = FakeS3(FILES, QUARANTINE)
    for key in keys:
        s3.put(FILES, key, "body of " + key, {"owner": "x"})
    return s3


def _quarantine(s3, orphans, bucket=QUARANTINE):
    return quarantine_orphans(
        s3,
        orphans,
        file_storage_bucket=FILES,
        quarantine_bucket=bucket,
        quarantine_prefix="quarantined",
        ds="2026-06-01",
    )


def _orphans(s3, *keys):
    return [_obj(k, len(s3.buckets[FILES][k]["body"])) for k in keys]


def test_quarantine_copies_verifies_then_deletes():
    s3 = _s3_with("files/a", "files/b")
    result = _quarantine(s3, _orphans(s3, "files/a"))
    assert (result.quarantined, result.failed) == (1, 0)
    assert s3.keys(FILES) == ["files/b"]
    assert s3.buckets[QUARANTINE]["quarantined/2026-06-01/files/a"]["metadata"] == {"owner": "x"}
    ops = [c[0] for c in s3.calls]
    assert ops == ["head", "copy", "head", "delete"]


def test_quarantine_overwrites_a_same_day_copy():
    s3 = _s3_with("files/dup.txt")
    s3.put(QUARANTINE, "quarantined/2026-06-01/files/dup.txt", "earlier copy")
    _quarantine(s3, _orphans(s3, "files/dup.txt"))
    body = s3.buckets[QUARANTINE]["quarantined/2026-06-01/files/dup.txt"]["body"]
    assert body == b"body of files/dup.txt"


def test_retry_skips_objects_already_quarantined():
    s3 = _s3_with("files/a", "files/b")
    orphans = _orphans(s3, "files/a", "files/b")
    s3.fail_delete = {"files/b"}
    first = _quarantine(s3, orphans)
    assert (first.moved, first.failed_keys) == (1, ["files/b"])
    retry = _quarantine(s3, orphans)
    assert (retry.moved, retry.already_quarantined, retry.failed) == (1, 1, 0)
    assert s3.keys(FILES) == []
    assert s3.keys(QUARANTINE) == [
        "quarantined/2026-06-01/files/a",
        "quarantined/2026-06-01/files/b",
    ]


def test_a_bad_copy_keeps_the_source():
    s3 = _s3_with("files/a")
    s3.short_copy = {"files/a"}
    result = _quarantine(s3, _orphans(s3, "files/a"))
    assert result.failed_keys == ["files/a"]
    assert s3.keys(FILES) == ["files/a"]
    assert not [c for c in s3.calls if c[0] == "delete"]


def test_per_object_failure_is_logged_at_error_and_the_rest_continue(caplog):
    s3 = _s3_with("files/a", "files/b", "files/c")
    s3.fail_copy = {"files/b"}
    with caplog.at_level("ERROR"):
        result = _quarantine(s3, _orphans(s3, "files/a", "files/b", "files/c"))
    assert (result.quarantined, result.failed_keys) == (2, ["files/b"])
    assert s3.keys(FILES) == ["files/b"]
    (event,) = (json.loads(r.message) for r in caplog.records if r.levelname == "ERROR")
    assert event["event"] == "quarantine_failed"
    assert event["source"] == f"s3://{FILES}/files/b"


def test_missing_quarantine_bucket_fails_every_object_and_keeps_them():
    s3 = _s3_with("files/a", "files/b")
    result = _quarantine(s3, _orphans(s3, "files/a", "files/b"), bucket="missing-bucket")
    assert (result.quarantined, result.failed) == (0, 2)
    assert s3.keys(FILES) == ["files/a", "files/b"]


def test_source_and_copy_both_missing_is_a_failure():
    s3 = _s3_with()
    result = _quarantine(s3, [_obj("files/gone")])
    assert result.failed_keys == ["files/gone"]


def test_retry_with_source_gone_fails_on_a_damaged_copy():
    s3 = _s3_with()
    s3.put(QUARANTINE, "quarantined/2026-06-01/files/a", "x" * 20)
    result = _quarantine(s3, [_obj("files/a", 100)])
    assert (result.already_quarantined, result.failed_keys) == (0, ["files/a"])
    assert s3.keys(QUARANTINE) == ["quarantined/2026-06-01/files/a"]


def test_retry_with_source_gone_accepts_a_full_size_copy():
    s3 = _s3_with()
    s3.put(QUARANTINE, "quarantined/2026-06-01/files/a", "x" * 100)
    result = _quarantine(s3, [_obj("files/a", 100)])
    assert (result.already_quarantined, result.failed) == (1, 0)


def _report(**overrides):
    args = {
        "ds": "2026-06-01",
        "generated_at": "2026-06-01T02:30:00+00:00",
        "total_objects": 8,
        "total_size_bytes": 171,
        "orphaned_objects": 6,
        "orphaned_bytes": 115,
        "objects_quarantined": 6,
        "objects_failed": 0,
        "quarantine_bucket": QUARANTINE,
        "price_per_gb_month_usd": 0.023,
        **overrides,
    }
    return build_report(**args)


def test_report_matches_legacy_fields_and_order():
    report = _report()
    assert list(report) == [
        "report_type",
        "report_date",
        "generated_at",
        "inventory",
        "orphans",
        "cleanup",
        "savings",
    ]
    assert report["orphans"] == {
        "orphaned_objects": 6,
        "orphaned_bytes": 115,
        "orphaned_size_gb": 0.0,
        "orphan_percentage": 75.0,
    }
    assert report["cleanup"] == {
        "objects_quarantined": 6,
        "objects_failed": 0,
        "quarantine_bucket": QUARANTINE,
    }
    assert "ContentType" not in json.dumps(report)


def test_report_percentage_is_int_zero_without_objects():
    report = _report(
        total_objects=0,
        total_size_bytes=0,
        orphaned_objects=0,
        orphaned_bytes=0,
        objects_quarantined=0,
    )
    pct = report["orphans"]["orphan_percentage"]
    assert pct == 0 and type(pct) is int
    assert type(_report()["orphans"]["orphan_percentage"]) is float


def test_storage_freed_counts_orphaned_bytes_even_when_copies_fail():
    report = _report(orphaned_bytes=3 * 1024**3, objects_quarantined=0, objects_failed=6)
    assert report["savings"] == {"storage_freed_gb": 3.0, "estimated_monthly_savings_usd": 0.069}
    assert report["cleanup"]["objects_failed"] == 6
