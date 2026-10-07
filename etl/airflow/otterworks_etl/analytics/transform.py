"""Analytics aggregation, ported from etl/scripts/analytics_daily.py.

Every function is pure (no I/O, no clock) so the DAG tasks stay thin and the legacy
behavior is unit-testable. The legacy quirks the goldens pin are reproduced on purpose;
each is marked "legacy:" and listed as a data-owner follow-up in the PR.
"""

from __future__ import annotations

import gzip
import io
import json
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd

USER_FIELDS = ("ownerId", "editedBy", "authorId", "deletedBy", "userId")
UNKNOWN_USER = "unknown"
TOP_USERS_LIMIT = 100
SUMMARY_FIELDS = (
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

UPSERT_SQL = """
    INSERT INTO analytics_daily_summary (
        report_date, active_users, active_documents, active_files,
        total_events, documents_created, documents_edited,
        comments_added, files_uploaded, files_shared,
        files_deleted, bytes_uploaded, updated_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
    )
    ON CONFLICT (report_date) DO UPDATE SET
        active_users = EXCLUDED.active_users,
        active_documents = EXCLUDED.active_documents,
        active_files = EXCLUDED.active_files,
        total_events = EXCLUDED.total_events,
        documents_created = EXCLUDED.documents_created,
        documents_edited = EXCLUDED.documents_edited,
        comments_added = EXCLUDED.comments_added,
        files_uploaded = EXCLUDED.files_uploaded,
        files_shared = EXCLUDED.files_shared,
        files_deleted = EXCLUDED.files_deleted,
        bytes_uploaded = EXCLUDED.bytes_uploaded,
        updated_at = NOW();
"""

_MALFORMED = object()


class NonObjectEventError(ValueError):
    """An event is valid JSON but not an object; legacy pandas.DataFrame raised on it."""


def parse_sqs_body(body: str) -> Any:
    """The decoded body, or ``None`` for a body legacy would leave in flight.

    Legacy accepts any valid JSON (scalars included, see ``aggregate_events``) and leaves
    bodies ``json.loads`` rejects undeleted.
    """
    try:
        return json.loads(body)
    except (TypeError, ValueError):
        return _MALFORMED


def is_malformed(parsed: Any) -> bool:
    return parsed is _MALFORMED


def native_dynamodb_item(item: Mapping[str, Any]) -> dict[str, Any]:
    """Top-level Decimals to int (when integral) or float, as legacy did."""
    out = dict(item)
    for key, value in out.items():
        if isinstance(value, Decimal):
            out[key] = int(value) if value == int(value) else float(value)
    return out


def _json_key(value: Any) -> str:
    """The object key ``json.dumps`` writes for a dict key (``nan`` -> ``"NaN"``)."""
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    try:
        return next(iter(json.loads(json.dumps({value: 0}))))
    except TypeError:
        return str(value)


def _parse_hour(ts: Any) -> str:
    # legacy: wall-clock hour of the timestamp's own offset; "00" for anything unparsable.
    if isinstance(ts, str):
        try:
            return "%02d" % datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
        except ValueError:
            pass
    return "00"


def _count(target: dict[Any, dict[str, int]], outer: Any, inner: str) -> None:
    bucket = target.setdefault(outer, {})
    bucket[inner] = bucket.get(inner, 0) + 1


def _unique(frame: pd.DataFrame, column: str) -> set:
    if column not in frame.columns:
        return set()
    return set(frame[column].dropna().unique())


def aggregate_events(events: Sequence[Any]) -> dict[str, Any] | None:
    """Legacy aggregation of SQS events followed by DynamoDB events; ``None`` if empty.

    Returns ``summary``, ``hourly_breakdown``, ``top_users``, ``document_metrics`` and
    ``file_metrics`` exactly as legacy wrote them (JSON-ready, string keys).
    """
    if not events:
        return None
    non_objects = [e for e in events if not isinstance(e, dict)]
    if non_objects:
        raise NonObjectEventError(
            "%d event(s) are JSON but not objects, e.g. %r" % (len(non_objects), non_objects[0])
        )

    df = pd.DataFrame(list(events))

    # legacy: event_type is only copied when *no* event has eventType, so DynamoDB items
    # (event_type) mixed with SQS bodies (eventType) are bucketed under NaN.
    if "event_type" in df.columns and "eventType" not in df.columns:
        df["eventType"] = df["event_type"]
    if "eventType" not in df.columns:
        df["eventType"] = "unknown"

    df["resolved_user_id"] = UNKNOWN_USER
    for col in USER_FIELDS:
        if col in df.columns:
            mask = (df["resolved_user_id"] == UNKNOWN_USER) & df[col].notna() & (df[col] != "")
            df.loc[mask, "resolved_user_id"] = df.loc[mask, col]

    df["hour"] = df["timestamp"].apply(_parse_hour) if "timestamp" in df.columns else "00"

    user_actions: dict[Any, dict[str, int]] = {}
    hourly: dict[str, dict[str, int]] = {}
    for uid, etype, hour in zip(df["resolved_user_id"], df["eventType"], df["hour"], strict=True):
        key = _json_key(etype)
        _count(user_actions, uid, key)
        _count(hourly, hour, key)

    # legacy: "unknown" is excluded from active_users but kept in top_users.
    active_users = set(df["resolved_user_id"].unique()) - {UNKNOWN_USER}
    top_users = sorted(
        (
            {"user_id": uid, "actions": actions, "total": sum(actions.values())}
            for uid, actions in user_actions.items()
        ),
        key=lambda u: u["total"],
        reverse=True,
    )[:TOP_USERS_LIMIT]

    by_type = {
        name: df[df["eventType"] == name]
        for name in (
            "document_created",
            "document_edited",
            "comment_added",
            "file_uploaded",
            "file_shared",
            "file_deleted",
        )
    }
    active_documents = _unique(by_type["document_created"], "documentId") | _unique(
        by_type["document_edited"], "documentId"
    )
    active_files = (
        _unique(by_type["file_uploaded"], "fileId")
        | _unique(by_type["file_shared"], "fileId")
        | _unique(by_type["file_deleted"], "fileId")
    )
    uploaded = by_type["file_uploaded"]
    # legacy: int() of the float sum truncates fractional byte sizes.
    bytes_uploaded = int(uploaded["sizeBytes"].fillna(0).sum()) if "sizeBytes" in df.columns else 0

    document_metrics = {
        "created": len(by_type["document_created"]),
        "edited": len(by_type["document_edited"]),
        "comments": len(by_type["comment_added"]),
    }
    file_metrics = {
        "uploaded": len(uploaded),
        "shared": len(by_type["file_shared"]),
        "deleted": len(by_type["file_deleted"]),
        "bytes_uploaded": bytes_uploaded,
    }
    summary = {
        "active_users": len(active_users),
        "active_documents": len(active_documents),
        "active_files": len(active_files),
        "total_events": len(events),
        "documents_created": document_metrics["created"],
        "documents_edited": document_metrics["edited"],
        "comments_added": document_metrics["comments"],
        "files_uploaded": file_metrics["uploaded"],
        "files_shared": file_metrics["shared"],
        "files_deleted": file_metrics["deleted"],
        "bytes_uploaded": bytes_uploaded,
    }
    return {
        "summary": summary,
        "hourly_breakdown": dict(sorted(hourly.items())),
        "top_users": top_users,
        "document_metrics": document_metrics,
        "file_metrics": file_metrics,
    }


def partition_key(prefix: str, ds: str) -> str:
    return f"{prefix}/year={ds[:4]}/month={ds[5:7]}/day={ds[8:10]}"


def data_lake_objects(aggregates: Mapping[str, Any], prefix: str, ds: str) -> dict[str, bytes]:
    """{key: gzip bytes} for the three data lake objects legacy wrote under the partition."""
    partition = partition_key(prefix, ds)
    users = io.BytesIO()
    with gzip.GzipFile(fileobj=users, mode="wb", mtime=0) as gz:
        for user in aggregates["top_users"]:
            gz.write(json.dumps(user).encode("utf-8"))
            gz.write(b"\n")
    return {
        f"{partition}/summary.json.gz": _gzip_json(aggregates["summary"]),
        f"{partition}/hourly_breakdown.json.gz": _gzip_json(aggregates["hourly_breakdown"]),
        f"{partition}/top_users.jsonl.gz": users.getvalue(),
    }


def _gzip_json(payload: Any) -> bytes:
    return gzip.compress(json.dumps(payload, indent=2).encode("utf-8"), mtime=0)


def upsert_parameters(summary: Mapping[str, Any], ds: str) -> tuple:
    return (ds, *(summary[field] for field in SUMMARY_FIELDS))


def build_report(
    aggregates: Mapping[str, Any], ds: str, generated_at: str, top_n: int
) -> dict[str, Any]:
    hourly = aggregates["hourly_breakdown"]
    peak_hour = None
    if hourly:
        hour, counts = max(hourly.items(), key=lambda item: sum(item[1].values()))
        peak_hour = {"hour": hour, "event_count": sum(counts.values())}
    return {
        "report_type": "daily_analytics",
        "report_date": ds,
        "generated_at": generated_at,
        "summary": aggregates["summary"],
        "highlights": {
            "peak_hour": peak_hour,
            "most_active_users": [u["user_id"] for u in aggregates["top_users"][:top_n]],
        },
        "document_metrics": aggregates["document_metrics"],
        "file_metrics": aggregates["file_metrics"],
    }
