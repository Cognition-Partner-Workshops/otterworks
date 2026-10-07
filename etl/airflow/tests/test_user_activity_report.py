from __future__ import annotations

import gzip
import json
from datetime import date
from decimal import Decimal

from otterworks_etl.user_activity import (
    SUMMARY_COLUMNS,
    SUMMARY_SQL,
    aggregate_user_days,
    build_report,
    day_keys,
    is_missing_bucket,
    is_postgres_config_error,
    report_objects,
    summary_parameters,
    summary_records,
    summary_rows,
)

DS = "2026-03-15"


def _day(*lines) -> bytes:
    return gzip.compress(
        "\n".join(x if isinstance(x, str) else json.dumps(x) for x in lines).encode()
    )


def _summary(report_date="2026-03-15", active_users=1, total_events=1):
    row = dict.fromkeys(SUMMARY_COLUMNS, 0)
    row.update(report_date=report_date, active_users=active_users, total_events=total_events)
    return row


def test_summary_query_keeps_the_legacy_inclusive_window_and_parameters():
    assert "BETWEEN %s::date - interval '%s days' AND %s::date" in SUMMARY_SQL
    assert "ORDER BY report_date" in SUMMARY_SQL
    assert summary_parameters(DS, 30) == (DS, 30, DS)


def test_summary_rows_are_json_safe_and_records_keep_column_order():
    rows = summary_rows([(date(2026, 3, 14), 2, 0, 0, 5, 0, 0, 0, 0, 0, 0, 10)])
    assert rows == [["2026-03-14", 2, 0, 0, 5, 0, 0, 0, 0, 0, 0, 10]]
    records = summary_records(rows)
    assert list(records[0]) == list(SUMMARY_COLUMNS)
    assert records[0]["report_date"] == "2026-03-14"


def test_s3_loop_reads_lookback_days_newest_first_one_fewer_than_sql():
    keys = day_keys("analytics/daily", DS, 30)
    assert len(keys) == 30
    assert keys[0] == "analytics/daily/year=2026/month=03/day=15/top_users.jsonl.gz"
    assert keys[-1] == "analytics/daily/year=2026/month=02/day=14/top_users.jsonl.gz"
    assert day_keys("analytics/daily", DS, 0) == []


def test_active_days_counts_lines_not_distinct_days():
    activity = aggregate_user_days(
        [_day({"user_id": "a", "total": 1}, {"user_id": "a", "total": 2})]
    )
    assert activity.totals["a"]["active_days"] == 2
    assert activity.totals["a"]["total_actions"] == 3


def test_bad_line_drops_rest_of_day_but_keeps_partial_totals():
    activity = aggregate_user_days(
        [
            _day({"user_id": "a", "total": 1}, "not json", {"user_id": "b", "total": 9}),
            _day({"user_id": "c", "total": "x"}),
            b"not gzip",
            _day({"user_id": "a", "total": 1, "actions": {"edit": 1}}),
        ]
    )
    assert set(activity.totals) == {"a", "c"}
    assert activity.totals["a"]["total_actions"] == 2
    # The entry is created before the failing += and stays, with zero totals.
    assert activity.totals["c"] == {
        "user_id": "c",
        "total_actions": 0,
        "active_days": 0,
        "actions_by_type": {},
    }
    assert (activity.days_read, activity.days_aborted) == (4, 3)


def test_null_user_id_stays_separate_from_missing_user_id():
    activity = aggregate_user_days([_day({"user_id": None, "total": 1}, {"total": 2})])
    assert set(activity.totals) == {None, "unknown"}


def test_blank_lines_are_skipped_and_actions_are_summed():
    activity = aggregate_user_days(
        [
            _day({"user_id": "a", "actions": {"x": 1, "y": 2}}, "", {"user_id": "a"}),
            _day({"user_id": "a", "total": 1.5, "actions": {"x": 0.5}}),
            gzip.compress(b""),
        ]
    )
    assert activity.totals["a"]["actions_by_type"] == {"x": 1.5, "y": 2}
    assert activity.totals["a"]["active_days"] == 3
    assert activity.days_aborted == 0


def test_users_sort_by_total_descending_and_ties_keep_first_seen_order():
    activity = aggregate_user_days(
        [
            _day(
                {"user_id": "b", "total": 1},
                {"user_id": "a", "total": 1},
                {"user_id": "c", "total": 5},
            )
        ]
    )
    assert [u["user_id"] for u in activity.users()] == ["c", "b", "a"]


def test_empty_report_has_int_zero_average():
    report = build_report([], [], DS, "t", 30)
    assert report["trends"] == {
        "total_events": 0,
        "peak_active_users": 0,
        "avg_daily_events": 0,
        "reporting_days": 0,
    }
    assert isinstance(report["trends"]["avg_daily_events"], int)


def test_total_users_is_peak_active_users_and_average_is_rounded_float():
    rows = [_summary("2026-03-13", 3, 10), _summary("2026-03-14", 7, 0), _summary(DS, 2, 1)]
    trends = build_report(rows, [], DS, "t", 30)["trends"]
    assert trends["peak_active_users"] == 7
    assert trends["avg_daily_events"] == 3.67
    assert trends["total_events"] == 11
    assert trends["reporting_days"] == 3
    assert isinstance(
        build_report([_summary()], [], DS, "t", 30)["trends"]["avg_daily_events"], float
    )


def test_report_shape_and_truncation():
    users = [
        {"user_id": i, "total_actions": 0, "active_days": 0, "actions_by_type": {}}
        for i in range(30)
    ]
    report = build_report([], users, DS, "2026-03-15T05:00:00+00:00", 30, 25, 3)
    assert list(report) == [
        "report_type",
        "report_date",
        "generated_at",
        "lookback_days",
        "trends",
        "daily_summaries",
        "user_summaries",
        "top_users",
    ]
    assert report["report_type"] == "user_activity" and report["report_date"] == DS
    assert len(report["user_summaries"]) == 25 and len(report["top_users"]) == 3


def test_report_objects_write_jsonl_first_and_render_like_legacy():
    users = [{"user_id": "a", "total_actions": 1, "active_days": 1, "actions_by_type": {}}]
    report = build_report([_summary()], users, DS, "t", 30)
    objects = report_objects(report, "reports/user-activity", DS)
    assert [k for k, _ in objects] == [
        "reports/user-activity/2026-03-15/user_summaries.jsonl",
        "reports/user-activity/2026-03-15/activity_report.json",
        "reports/user-activity/latest/activity_report.json",
    ]
    legacy = json.dumps(report, indent=2, default=str)
    assert objects[1][1] == objects[2][1] == legacy
    assert objects[0][1] == json.dumps(users[0], default=str) + "\n"


def test_no_users_means_no_jsonl():
    objects = report_objects(build_report([], [], DS, "t", 30), "p", DS)
    assert [k for k, _ in objects] == [
        "p/2026-03-15/activity_report.json",
        "p/latest/activity_report.json",
    ]


def test_decimal_values_render_with_default_str():
    report = build_report([{**_summary(), "bytes_uploaded": Decimal("1.5")}], [], DS, "t", 30)
    assert '"bytes_uploaded": "1.5"' in report_objects(report, "p", DS)[0][1]


class _PgError(Exception):
    def __init__(self, message, pgcode=None):
        super().__init__(message)
        self.pgcode = pgcode


def test_postgres_config_errors_are_recognised():
    assert is_postgres_config_error(_PgError('database "x" does not exist'))
    assert is_postgres_config_error(_PgError("boom", pgcode="28P01"))
    assert is_postgres_config_error(_PgError("password authentication failed for user"))
    assert not is_postgres_config_error(_PgError("could not connect to server: Connection refused"))
    assert not is_postgres_config_error(_PgError("canceling statement", pgcode="57014"))


class _ClientError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


def test_missing_bucket_is_recognised_from_client_and_upload_errors():
    assert is_missing_bucket(_ClientError("NoSuchBucket"))
    assert is_missing_bucket(
        Exception("Failed to upload: An error occurred (NoSuchBucket) when calling PutObject")
    )
    assert not is_missing_bucket(_ClientError("AccessDenied"))
