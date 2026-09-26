"""MongoDB backend for the usage-events slice of the billing facade.

Covers /internal/usage/events writes and the summary/events half of
/api/v1/billing/usage. Rating (unit u-09) is not in this batch, so the facade
returns rating=[] for this backend. USAGE_KINDS mirrors CODES(USAGE_KIND) and
the DECODE in pkg_rating.fn_usage_summary because the codes table is not one
of this unit's write targets. Number rendering matches oracle._json_value:
oracledb with fetch_decimals returns Decimal, rendered as str.
"""

import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal

NAME = "mongo"

USAGE_KINDS = {"api": 1, "storage": 2, "compute": 3}
_KIND_LABELS = {code: label for label, code in USAGE_KINDS.items()}

_client = None


def _get_client():
    global _client
    if _client is None:
        from pymongo import MongoClient

        _client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    return _client


def _db():
    return _get_client()[os.getenv("MONGO_DB", "ow_billing_migration")]


def _collection(name):
    return _db()[name]


def is_unavailable(exc):
    from pymongo.errors import PyMongoError

    return isinstance(exc, PyMongoError)


def usage_kind_code(kind):
    return USAGE_KINDS.get(kind)


def health():
    _get_client().admin.command("ping")


def record_usage_event(event_id, tenant_id, occurred_at, units, kind):
    from bson.int64 import Int64
    from pymongo.errors import DuplicateKeyError

    if units is None or units <= 0:
        raise ValueError("units must be > 0")
    kind_cd = usage_kind_code(kind)
    if kind_cd is None:
        raise ValueError(f"unknown usage kind {kind}")
    if isinstance(occurred_at, str):
        occurred_at = (
            datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
            .replace(tzinfo=None)
        )
    occurred_at = occurred_at.replace(
        microsecond=(occurred_at.microsecond // 1000) * 1000
    )
    try:
        _collection("usageEvents").insert_one(
            {
                "_id": event_id,
                "tenantId": tenant_id,
                "occurredAt": occurred_at,
                "units": Int64(units),
                "kindCd": Int64(kind_cd),
            }
        )
    except DuplicateKeyError:
        return "duplicate"
    return "recorded"


def _day_start(value):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return datetime.combine(date.fromisoformat(str(value)), time.min)


def _day_after_end(value):
    return _day_start(value) + timedelta(days=1)


def _json_value(value):
    if isinstance(value, datetime):
        if value.time() == time.min:
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    return value


def usage_events(tenant_id, start, end):
    cursor = (
        _collection("usageEvents")
        .find(
            {
                "tenantId": tenant_id,
                "occurredAt": {
                    "$gte": _day_start(start),
                    "$lt": _day_after_end(end),
                },
            }
        )
        .sort([("occurredAt", -1), ("_id", -1)])
        .limit(50)
    )
    return [
        {
            "id": doc["_id"],
            "occurred_at": _json_value(doc["occurredAt"]),
            "units": _json_value(doc["units"]),
            "kind": _KIND_LABELS.get(int(doc["kindCd"]), "UNKNOWN"),
        }
        for doc in cursor
    ]


def usage_summary(tenant_id, start, end):
    pipeline = [
        {
            "$match": {
                "tenantId": tenant_id,
                "occurredAt": {
                    "$gte": _day_start(start),
                    "$lt": _day_after_end(end),
                },
            }
        },
        {
            "$group": {
                "_id": "$kindCd",
                "event_count": {"$sum": 1},
                "units": {"$sum": "$units"},
            }
        },
    ]
    rows = [
        {
            "kind": _KIND_LABELS.get(int(group["_id"]), "UNKNOWN"),
            "event_count": str(group["event_count"]),
            "units": str(int(group["units"])),
        }
        for group in _collection("usageEvents").aggregate(pipeline)
    ]
    rows.sort(key=lambda row: row["kind"])
    return rows
