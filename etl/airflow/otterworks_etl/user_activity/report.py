"""Pure query, aggregation and rendering logic for the otterworks_user_activity_report DAG.

Every legacy quirk of ``etl/scripts/user_activity_daily.py`` is kept on purpose so the DAG
matches the s1.5 goldens; each one is a data-owner follow-up listed in the PR.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

SUMMARY_COLUMNS = (
    "report_date",
    "active_users",
    "active_documents",
    "active_files",
    "total_events",
    "documents_created",
    "documents_edited",
    "comments_added",
    "files_uploaded",
    "files_shared",
    "files_deleted",
    "bytes_uploaded",
)

# Same text and parameters as the legacy script. The window is inclusive at both ends, so it
# covers lookback_days + 1 dates while the S3 loop below reads only lookback_days.
SUMMARY_SQL = """
    SELECT
        report_date,
        active_users,
        active_documents,
        active_files,
        total_events,
        documents_created,
        documents_edited,
        comments_added,
        files_uploaded,
        files_shared,
        files_deleted,
        bytes_uploaded
    FROM analytics_daily_summary
    WHERE report_date BETWEEN %s::date - interval '%s days' AND %s::date
    ORDER BY report_date;
"""

# libpq / server errors that a retry cannot fix.
_CONFIG_SQLSTATES = {"28000", "28P01", "3D000", "42P01"}
_CONFIG_MESSAGES = (
    "password authentication failed",
    "no pg_hba.conf entry",
    "does not exist",
    "role ",
)


def summary_parameters(ds: str, lookback_days: int) -> tuple[str, int, str]:
    return (ds, lookback_days, ds)


def summary_rows(records: Iterable[Sequence[Any]]) -> list[list[Any]]:
    """``get_records`` rows as JSON-safe lists (dates to ISO strings), in column order."""
    rows = []
    for record in records:
        rows.append([v.isoformat() if hasattr(v, "isoformat") else v for v in record])
    return rows


def summary_records(rows: Iterable[Sequence[Any]]) -> list[dict[str, Any]]:
    return [dict(zip(SUMMARY_COLUMNS, row, strict=True)) for row in rows]


def day_keys(prefix: str, ds: str, lookback_days: int) -> list[str]:
    """``top_users.jsonl.gz`` partition keys, newest first, for ``range(lookback_days)``."""
    run_date = datetime.strptime(ds, "%Y-%m-%d")
    keys = []
    for offset in range(lookback_days):
        day = run_date - timedelta(days=offset)
        keys.append(f"{prefix}/year={day:%Y}/month={day:%m}/day={day:%d}/top_users.jsonl.gz")
    return keys


@dataclass
class UserActivity:
    """Per-user totals in first-seen order, plus how many day files ended early."""

    totals: dict[Any, dict[str, Any]] = field(default_factory=dict)
    days_read: int = 0
    days_aborted: int = 0

    def users(self) -> list[dict[str, Any]]:
        return sorted(self.totals.values(), key=lambda u: u["total_actions"], reverse=True)


def accumulate_day(activity: UserActivity, body: bytes) -> bool:
    """Fold one day's gzipped JSONL into ``activity`` with the legacy semantics.

    ``active_days`` counts lines, so a user listed twice on one day counts twice. A bad line
    (or a body that is not gzip/UTF-8) stops the rest of that file, keeping what was already
    added, including a user entry created just before the failing ``+=``. Returns False when
    the file ended early.
    """
    activity.days_read += 1
    try:
        lines = gzip.decompress(body).decode("utf-8").strip().split("\n")
        for line in lines:
            if not line:
                continue
            user_data = json.loads(line)
            uid = user_data.get("user_id", "unknown")
            total = user_data.get("total", 0)
            if uid not in activity.totals:
                activity.totals[uid] = {
                    "user_id": uid,
                    "total_actions": 0,
                    "active_days": 0,
                    "actions_by_type": {},
                }
            activity.totals[uid]["total_actions"] += total
            activity.totals[uid]["active_days"] += 1
            for action_type, count in user_data.get("actions", {}).items():
                by_type = activity.totals[uid]["actions_by_type"]
                by_type[action_type] = by_type.get(action_type, 0) + count
    except Exception:
        activity.days_aborted += 1
        return False
    return True


def aggregate_user_days(bodies: Iterable[bytes]) -> UserActivity:
    activity = UserActivity()
    for body in bodies:
        accumulate_day(activity, body)
    return activity


def build_report(
    daily_summaries: list[dict[str, Any]],
    user_list: list[dict[str, Any]],
    ds: str,
    generated_at: str,
    lookback_days: int,
    max_user_summaries: int = 500,
    top_users: int = 20,
) -> dict[str, Any]:
    total_events = sum(d.get("total_events", 0) for d in daily_summaries)
    peak_active_users = max((d.get("active_users", 0) for d in daily_summaries), default=0)
    avg_daily_events = total_events / len(daily_summaries) if daily_summaries else 0
    return {
        "report_type": "user_activity",
        "report_date": ds,
        "generated_at": generated_at,
        "lookback_days": lookback_days,
        "trends": {
            "total_events": total_events,
            "peak_active_users": peak_active_users,
            "avg_daily_events": round(avg_daily_events, 2),
            "reporting_days": len(daily_summaries),
        },
        "daily_summaries": daily_summaries,
        "user_summaries": user_list[:max_user_summaries],
        "top_users": user_list[:top_users],
    }


def report_objects(report: Mapping[str, Any], prefix: str, ds: str) -> list[list[str]]:
    """``[key, body]`` pairs in write order: the JSONL first, so ``latest/`` never points at
    a dated report whose JSONL is missing. Bodies are rendered exactly as the legacy script."""
    body = json.dumps(report, indent=2, default=str)
    objects = []
    user_summaries = report["user_summaries"]
    if user_summaries:
        jsonl = "\n".join(json.dumps(u, default=str) for u in user_summaries) + "\n"
        objects.append([f"{prefix}/{ds}/user_summaries.jsonl", jsonl])
    objects.append([f"{prefix}/{ds}/activity_report.json", body])
    objects.append([f"{prefix}/latest/activity_report.json", body])
    return objects


def is_postgres_config_error(exc: BaseException) -> bool:
    """True for errors a retry cannot fix (bad credentials, missing database or table)."""
    if getattr(exc, "pgcode", None) in _CONFIG_SQLSTATES:
        return True
    message = str(exc).lower()
    return any(m in message for m in _CONFIG_MESSAGES)


def is_missing_bucket(exc: BaseException) -> bool:
    """True when an S3 write failed because the bucket does not exist."""
    response = getattr(exc, "response", None)
    if isinstance(response, Mapping):
        if response.get("Error", {}).get("Code") == "NoSuchBucket":
            return True
    return "NoSuchBucket" in str(exc)
