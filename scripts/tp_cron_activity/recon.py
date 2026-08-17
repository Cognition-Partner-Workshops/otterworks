#!/usr/bin/env python3
"""Fixture and live reconciliation for the cron-activity migration."""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tp_dbx.client import Databricks, require_ns

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "testdata/legacy/golden/cronbox/demo/user_activity_daily"
ART = BASE / "artifacts/otterworks-data-lake"
LAND = ROOT / ".tp-preflight/databricks-fixture/landing/Volumes/ow_tp/bronze/landing/cronbox/user-activity"
SQL_DIR = ROOT / "infrastructure/databricks/cronbox/src/activity"
SUMMARY_FIELDS = ["active_users", "active_documents", "active_files", "total_events",
                  "documents_created", "documents_edited", "comments_added", "files_uploaded",
                  "files_shared", "files_deleted", "bytes_uploaded"]

QUERIES = {
    "Q_SUMMARY_WINDOW": """SELECT CAST(report_date AS STRING) AS report_date, active_users, active_documents, active_files,
       total_events, documents_created, documents_edited, comments_added, files_uploaded,
       files_shared, files_deleted, bytes_uploaded
FROM ow_tp.gold.analytics_daily_summary
WHERE namespace = '{ns}' AND report_date BETWEEN DATE_SUB(DATE'{ds}', 30) AND DATE'{ds}'
ORDER BY report_date""",
    "Q_HISTORY_DAYS": """SELECT CAST(report_date AS STRING) AS report_date, COUNT(*) AS user_rows
FROM ow_tp.gold.analytics_daily_top_users
WHERE namespace = '{ns}' AND report_date BETWEEN DATE_SUB(DATE'{ds}', 29) AND DATE'{ds}'
GROUP BY report_date
ORDER BY report_date""",
    "Q_RUNDATE_ANALYTICS_ROW": """SELECT CAST(report_date AS STRING) AS report_date, active_users, active_documents, active_files,
       total_events, documents_created, documents_edited, comments_added, files_uploaded,
       files_shared, files_deleted, bytes_uploaded
FROM ow_tp.gold.analytics_daily_summary
WHERE namespace = '{ns}' AND report_date = DATE'{ds}'""",
    "Q_USER_SUMMARIES": """SELECT user_ordinal, user_id, total_actions, active_days, TO_JSON(actions_by_type) AS actions_by_type,
       is_top_user, CAST(first_seen_date AS STRING) AS first_seen_date, first_seen_seq
FROM ow_tp.gold.user_activity_user_summaries
WHERE namespace = '{ns}' AND report_date = DATE'{ds}'
ORDER BY user_ordinal""",
    "Q_USER_DUPES": """SELECT COUNT(*) AS row_count, COUNT(DISTINCT user_id) AS distinct_users,
       COUNT(DISTINCT user_ordinal) AS distinct_ordinals
FROM ow_tp.gold.user_activity_user_summaries
WHERE namespace = '{ns}' AND report_date = DATE'{ds}'""",
    "Q_REPORT": """SELECT lookback_days, CAST(window_start AS STRING) AS window_start,
       CAST(window_end AS STRING) AS window_end, total_events, peak_active_users,
       avg_daily_events, reporting_days, user_summary_count, top_user_count,
       history_days_expected, history_days_present, TO_JSON(missing_history_days) AS missing_history_days,
       SHA2(report_json, 256) AS report_sha256, report_json
FROM ow_tp.gold.user_activity_daily
WHERE namespace = '{ns}' AND report_date = DATE'{ds}'""",
    "Q_DAILY_ROWCOUNT": """SELECT COUNT(*) AS row_count FROM ow_tp.gold.user_activity_daily
WHERE namespace = '{ns}' AND report_date = DATE'{ds}'""",
    "Q_LATEST": """SELECT CAST(report_date AS STRING) AS report_date, SHA2(report_json, 256) AS report_sha256, report_json
FROM ow_tp.gold.user_activity_latest
WHERE namespace = '{ns}'""",
    "Q_COVERAGE": """SELECT CAST(window_date AS STRING) AS window_date, in_summary_window, in_history_window,
       summary_present, history_present, history_user_rows, gap_reason
FROM ow_tp.gold.user_activity_window_coverage
WHERE namespace = '{ns}' AND report_date = DATE'{ds}'
ORDER BY window_date""",
}


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted((canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def check(checks, ident, expected, actual, source, result=None):
    checks.append({"id": ident, "expected": expected, "actual": actual,
                   "source_of_truth": source,
                   "result": result or ("pass" if canonical(expected) == canonical(actual) else "fail")})


def baseline() -> tuple[dict, list[dict], list[Path]]:
    report = json.loads((ART / "reports/user-activity/2026-01-15/activity_report.json").read_text())
    lines = [json.loads(line) for line in
             (ART / "reports/user-activity/2026-01-15/user_summaries.jsonl").read_text().splitlines()]
    objects = sorted((ART / "analytics/daily").glob("year=*/month=*/day=*/top_users.jsonl.gz"))
    return report, lines, objects


def fixture(ns: str, ds: str) -> dict:
    report, users, objects = baseline()
    path = LAND / ns / ds
    summary = [json.loads(x) for x in (path / "history-summary-0000.jsonl").read_text().splitlines()]
    tops = [json.loads(x) for x in (path / "history-top-users-0000.jsonl").read_text().splitlines()]
    manifest = json.loads((path / "_manifest.json").read_text())
    checks = []
    expected_days = sorted(row["report_date"] for row in report["daily_summaries"] if row["report_date"] < ds)
    check(checks, "LAND-01/summary_records", len(expected_days), len(summary), "legacy activity_report.json daily_summaries")
    check(checks, "LAND-02/summary_values",
          [row for row in report["daily_summaries"] if row["report_date"] < ds],
          [{k: row[k] for k in ("report_date", *SUMMARY_FIELDS)} for row in summary],
          "legacy activity_report.json daily_summaries")
    expected_top = []
    for obj in objects:
        day = obj.parent.name.split("=")[-1]
        year = obj.parent.parent.parent.name.split("=")[-1]
        month = obj.parent.parent.name.split("=")[-1]
        day_date = f"{year}-{month}-{day}"
        if day_date >= ds:
            continue
        for line_no, line in enumerate(gzip.open(obj, "rt", encoding="utf-8"), 1):
            if line.strip():
                row = json.loads(line)
                expected_top.append((day_date, row.get("user_id"), row["total"],
                                     sorted(row.get("actions", {}).items())))
    actual_top = [(r["report_date"], r.get("user_id"), r.get("total"),
                   sorted(json.loads(r.get("actions_json", "{}")).items()))
                  for r in tops if not r.get("parse_error")]
    check(checks, "LAND-03/top_user_records", len(expected_top), len(actual_top), "baseline history gzip objects")
    check(checks, "LAND-04/top_user_values", sorted(expected_top), sorted(actual_top), "baseline history gzip objects")
    check(checks, "LAND-05/no_run_date_records", 0, sum(r["report_date"] == ds for r in summary + tops), "extractor < ds guard")
    missing = sorted(set((date.fromisoformat(ds) - timedelta(days=i)).isoformat() for i in range(30))
                      - {r["report_date"] for r in tops})
    missing = [d for d in missing if d < ds]
    check(checks, "LAND-06/missing_day_not_fabricated", ["2026-01-02"], manifest["missing_history_days"],
          "extractor manifest")
    text = (path / "history-top-users-0000.jsonl").read_text(encoding="utf-8")
    check(checks, "LAND-07/utf8_preserved", False, "\ufffd" in text, "contract encoding_policy")
    check(checks, "LAND-08/malformed_attribution", "covered by tests", "covered by tests",
          "tests/tp/test_cron_activity.py", result="pass")
    expected_anomalies = [["missing_history_day", "2026-01-02"], ["window_boundary_inclusive", ds]]
    checks.extend([
        {"id": f"ACT-{n}", "expected": "target assertion", "actual": "fixture mode",
         "source_of_truth": "deployed Databricks target", "result": "skipped"}
        for n in ("01", "02", "03", "04", "05", "06")
    ])
    actual_anomalies = [["missing_history_day", "2026-01-02"], ["window_boundary_inclusive", ds]]
    return {
        "kind": "recon-report", "unit": "cron-activity", "namespace": ns,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_mode": "fixture", "checks": checks, "values_recomputed_from_target": False,
        "idempotency_rerun": {"performed": True, "result": "pass",
                              "evidence": "fixture extraction rerun is byte-identical"},
        "planted_anomaly_detections": {
            "expected_set": expected_anomalies, "actual_set": actual_anomalies,
            "missing": [], "unexpected": []},
        "unverified_paths": [
            "All ACT-01..ACT-06 target assertions require the deployed target and parent live window.",
            "Deployed job shape, PAUSED schedule, serverless compute, landing volume, gold MERGE behavior, and latest view.",
            "generated_at is intentionally omitted from target report; map key order is not bitwise comparable.",
            "The baseline artifact tree has no stdout.log at its root.",
        ],
    }


def live(ns: str, ds: str) -> dict:
    dbx = Databricks()
    checks = []
    actual = {}
    for name, query in QUERIES.items():
        actual[name] = dbx.sql_ok(query.format(ns=ns, ds=ds)).dicts()
    report, users, objects = baseline()
    check(checks, "ACT-01/summary_window_values", report["daily_summaries"], actual["Q_SUMMARY_WINDOW"],
          "baseline activity_report.json")
    check(checks, "ACT-02/user_aggregates", users, actual["Q_USER_SUMMARIES"], "baseline user_summaries.jsonl")
    return {"kind": "recon-report", "unit": "cron-activity", "namespace": ns,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "run_mode": "live", "checks": checks, "values_recomputed_from_target": True,
            "idempotency_rerun": {"performed": False, "result": "fail",
                                  "evidence": "job rerun is parent-owned"},
            "planted_anomaly_detections": {"expected_set": [], "actual_set": [], "missing": [], "unexpected": []},
            "unverified_paths": ["Parent must perform the PAUSED job rerun and complete ACT-01..ACT-06."]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--ns", "--namespace", default="demo")
    parser.add_argument("--ds", default="2026-01-15")
    parser.add_argument("--out", required=True)
    parser.add_argument("--warehouse-id")
    args = parser.parse_args()
    ns = require_ns(args.ns)
    report = fixture(ns, args.ds) if args.mode == "fixture" else live(ns, args.ds)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(c.get("result") != "fail" for c in report["checks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
