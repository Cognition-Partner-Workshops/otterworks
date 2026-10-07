from __future__ import annotations

import gzip
import json
import math
from decimal import Decimal

import pytest

from otterworks_etl.analytics import (
    NonObjectEventError,
    aggregate_events,
    build_report,
    data_lake_objects,
    native_dynamodb_item,
    parse_sqs_body,
    partition_key,
    upsert_parameters,
)
from otterworks_etl.analytics.transform import SUMMARY_FIELDS, is_malformed


def test_parse_sqs_body_keeps_any_json_and_flags_the_rest():
    assert parse_sqs_body('{"eventType": "page_view"}') == {"eventType": "page_view"}
    assert parse_sqs_body("42") == 42
    for body in ("this is not json", '{"eventType": ', "<event/>"):
        assert is_malformed(parse_sqs_body(body))


def test_native_dynamodb_item_converts_top_level_decimals():
    item = native_dynamodb_item({"a": Decimal("300"), "b": Decimal("10.5"), "c": "x"})
    assert item == {"a": 300, "b": 10.5, "c": "x"}
    assert isinstance(item["a"], int)


def test_empty_input_aggregates_to_none():
    assert aggregate_events([]) is None


def test_non_object_event_raises():
    with pytest.raises(NonObjectEventError):
        aggregate_events([{"eventType": "page_view"}, 42])


def test_event_type_copied_only_when_no_event_has_event_type_camel_case():
    dynamo_only = aggregate_events([{"event_type": "file_uploaded", "userId": "u"}])
    assert dynamo_only["hourly_breakdown"] == {"00": {"file_uploaded": 1}}

    # legacy: mixed with SQS bodies the DynamoDB event_type is lost under NaN.
    mixed = aggregate_events(
        [{"eventType": "page_view", "userId": "u"}, {"event_type": "file_uploaded", "userId": "u"}]
    )
    assert mixed["hourly_breakdown"] == {"00": {"NaN": 1, "page_view": 1}}
    assert mixed["top_users"] == [
        {"user_id": "u", "actions": {"page_view": 1, "NaN": 1}, "total": 2}
    ]

    neither = aggregate_events([{"userId": "u"}])
    assert neither["hourly_breakdown"] == {"00": {"unknown": 1}}


def test_user_precedence_skips_empty_strings_and_counts_unknown():
    result = aggregate_events(
        [
            {"eventType": "comment_added", "ownerId": "", "authorId": "hank", "userId": "x"},
            {"eventType": "comment_added", "ownerId": "owner", "authorId": "ivy"},
            {"eventType": "page_view"},
            {"eventType": "page_view"},
        ]
    )
    users = {u["user_id"]: u["total"] for u in result["top_users"]}
    assert users == {"hank": 1, "owner": 1, "unknown": 2}
    assert result["top_users"][0]["user_id"] == "unknown"
    assert result["summary"]["active_users"] == 2


def test_hour_is_local_to_the_timestamp_offset_and_00_when_unparsable():
    result = aggregate_events(
        [
            {"eventType": "e", "timestamp": "2026-03-15T08:05:00Z"},
            {"eventType": "e", "timestamp": "2026-03-15T10:00:00+05:00"},
            {"eventType": "e", "timestamp": "2026-03-15 11:45:00"},
            {"eventType": "e", "timestamp": "not-a-timestamp"},
            {"eventType": "e", "timestamp": 1773568800},
            {"eventType": "e"},
        ]
    )
    assert result["hourly_breakdown"] == {
        "00": {"e": 3},
        "08": {"e": 1},
        "10": {"e": 1},
        "11": {"e": 1},
    }
    assert list(result["hourly_breakdown"]) == ["00", "08", "10", "11"]


def test_document_and_file_metrics_and_truncated_bytes():
    result = aggregate_events(
        [
            {"eventType": "document_created", "documentId": "d1"},
            {"eventType": "document_edited", "documentId": "d1"},
            {"eventType": "document_edited", "documentId": "d2"},
            {"eventType": "comment_added", "documentId": "d3"},
            {"eventType": "file_uploaded", "fileId": "f1", "sizeBytes": 10.5},
            {"eventType": "file_uploaded", "fileId": "f2", "sizeBytes": 300},
            {"eventType": "file_uploaded", "fileId": "f3"},
            {"eventType": "file_shared", "fileId": "f1", "sizeBytes": 999},
            {"eventType": "file_deleted", "fileId": "f4"},
        ]
    )
    assert result["document_metrics"] == {"created": 1, "edited": 2, "comments": 1}
    assert result["file_metrics"] == {
        "uploaded": 3,
        "shared": 1,
        "deleted": 1,
        "bytes_uploaded": 310,
    }
    summary = result["summary"]
    assert summary["active_documents"] == 2  # comments do not count
    assert summary["active_files"] == 4
    assert summary["total_events"] == 9
    assert set(summary) == set(SUMMARY_FIELDS)


def test_top_users_ties_keep_first_appearance_and_cap_at_100():
    events = [{"eventType": "e", "userId": f"u{i:03d}"} for i in range(150)]
    events += [{"eventType": "e", "userId": "u149"}]
    top = aggregate_events(events)["top_users"]
    assert len(top) == 100
    assert top[0]["user_id"] == "u149"
    assert [u["user_id"] for u in top[1:4]] == ["u000", "u001", "u002"]


def test_aggregates_are_json_ready():
    result = aggregate_events([{"eventType": "e", "userId": "u"}, {"event_type": "x"}])
    assert json.loads(json.dumps(result, sort_keys=True)) == result


def test_data_lake_objects_match_legacy_layout():
    aggregates = aggregate_events([{"eventType": "page_view", "userId": "u"}])
    objects = data_lake_objects(aggregates, "analytics/daily", "2026-03-15")
    base = "analytics/daily/year=2026/month=03/day=15"
    assert partition_key("analytics/daily", "2026-03-15") == base
    assert sorted(objects) == [
        f"{base}/hourly_breakdown.json.gz",
        f"{base}/summary.json.gz",
        f"{base}/top_users.jsonl.gz",
    ]
    assert json.loads(gzip.decompress(objects[f"{base}/summary.json.gz"])) == aggregates["summary"]
    users = gzip.decompress(objects[f"{base}/top_users.jsonl.gz"]).decode()
    assert users.endswith("\n")
    assert [json.loads(line) for line in users.splitlines()] == aggregates["top_users"]
    assert objects == data_lake_objects(aggregates, "analytics/daily", "2026-03-15")


def test_upsert_parameters_order_matches_sql():
    summary = {field: i for i, field in enumerate(SUMMARY_FIELDS)}
    assert upsert_parameters(summary, "2026-03-15") == ("2026-03-15", *range(len(SUMMARY_FIELDS)))


def test_build_report_peak_hour_and_top_n():
    aggregates = aggregate_events(
        [
            {"eventType": "a", "userId": "u1", "timestamp": "2026-03-15T13:00:00Z"},
            {"eventType": "b", "userId": "u1", "timestamp": "2026-03-15T13:10:00Z"},
            {"eventType": "a", "userId": "u2", "timestamp": "2026-03-15T09:00:00Z"},
        ]
    )
    report = build_report(aggregates, "2026-03-15", "2026-03-15T02:00:00+00:00", top_n=1)
    assert report["highlights"] == {
        "peak_hour": {"hour": "13", "event_count": 2},
        "most_active_users": ["u1"],
    }
    assert report["report_type"] == "daily_analytics"
    assert report["report_date"] == "2026-03-15"
    assert report["summary"] is aggregates["summary"]


def test_nan_key_is_a_string_not_a_float():
    result = aggregate_events([{"eventType": "e"}, {"event_type": "x"}])
    keys = list(result["hourly_breakdown"]["00"])
    assert "NaN" in keys
    assert not any(isinstance(k, float) and math.isnan(k) for k in keys)
