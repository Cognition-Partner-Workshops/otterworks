from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path

from scripts.tp_cron_activity.extract_history import aggregate_history, dates, parse_history

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "testdata/legacy/golden/cronbox/demo/user_activity_daily/artifacts/otterworks-data-lake"


def test_windows_include_run_date_and_summary_has_thirty_one_dates():
    values = dates("2026-01-15")
    assert len(values) == 30
    assert values[0] == date(2026, 1, 15)
    assert values[-1] == date(2025, 12, 17)
    assert (date(2026, 1, 15) - date(2025, 12, 17)).days == 29


def test_parse_history_guard_and_missing_day_are_nonfatal():
    key = "analytics/daily/year=2026/month=01/day=14/top_users.jsonl.gz"
    records = parse_history("demo", date(2026, 1, 14), key, gzip.compress(b'{"user_id":"u","total":1,"actions":{}}\n'))
    assert records[0]["report_date"] == "2026-01-14"
    assert "2026-01-15" not in {record["report_date"] for record in records}


def test_malformed_and_invalid_utf8_are_attributed():
    key = "analytics/daily/year=2026/month=01/day=14/top_users.jsonl.gz"
    records = parse_history("demo", date(2026, 1, 14), key,
                            gzip.compress(b'not-json\n{"user_id":"u","total":1,"actions":{}}\n'))
    assert records[0]["parse_error"]
    assert records[0]["source_object"] == key
    assert records[0]["source_line"] == 1
    invalid = parse_history("demo", date(2026, 1, 14), key, b"\x1f\x8bnot-utf8")
    assert invalid[0]["parse_error"]
    assert invalid[0]["source_line"] == 1


def test_extra_fields_and_missing_user_are_tolerated_and_attributed():
    key = "history.gz"
    records = parse_history("demo", date(2026, 1, 14), key,
                            gzip.compress(b'{"total":2,"actions":{"edit":2},"extra":"ok"}\n'))
    assert aggregate_history(records)[0]["user_id"] == "unknown"
    assert aggregate_history(records)[0]["active_days"] == 1


def test_ordering_replays_baseline_and_map_values():
    report = json.loads((BASE / "reports/user-activity/2026-01-15/activity_report.json").read_text())
    expected = [row["user_id"] for row in report["user_summaries"]]
    records = []
    for path in sorted((BASE / "analytics/daily").glob("year=*/month=*/day=*/top_users.jsonl.gz")):
        day = "-".join(part.split("=")[1] for part in path.parent.parts[-3:])
        if day > "2026-01-15":
            continue
        for line_no, line in enumerate(gzip.open(path, "rt", encoding="utf-8"), 1):
            row = json.loads(line)
            records.append({"report_date": day, "source_line": line_no, **row,
                            "actions_json": json.dumps(row.get("actions", {}))})
    actual = aggregate_history(records)
    assert [row["user_id"] for row in actual] == expected
    assert [(row["total_actions"], row["active_days"]) for row in actual] == [
        (row["total_actions"], row["active_days"]) for row in report["user_summaries"]
    ]


def test_trends_rounding_and_empty_result():
    report = json.loads((BASE / "reports/user-activity/2026-01-15/activity_report.json").read_text())
    assert round(report["trends"]["total_events"] / report["trends"]["reporting_days"], 2) == 33.27
    assert aggregate_history([]) == []
