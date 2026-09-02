"""Application-side equivalents of PKG_OW_UTIL."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone

from bson import Int64
from pymongo import ReturnDocument, WriteConcern
from pymongo.errors import PyMongoError

from . import NS_VALUE

SEQ_BILLING_AUDIT_LOG = "seq_billing_audit_log"
SEQ_SUBSCRIPTIONS_HIST = "seq_subscriptions_hist"
AUDIT_WRITE_CONCERN = WriteConcern(w="majority")
MONTHS = (
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
)
DATE_TEXT = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{2})$")


def f_md5_uuid(value: str) -> str:
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()
    return (
        f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-"
        f"{digest[16:20]}-{digest[20:]}"
    )


def f_code_desc(store, code_type: str, code_val: int | None) -> str | None:
    doc = store.coll("codes").find_one(
        {"code_type": code_type, "code_val": code_val},
        {"code_desc": 1},
    )
    if doc is None:
        return f"UNKNOWN({code_val if code_val is not None else -1})"
    return doc.get("code_desc")


def f_dt2str(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    return f"{dt.day:02d}-{MONTHS[dt.month - 1]}-{dt.year % 100:02d}"


def f_str2dt(text: str | None) -> datetime | None:
    if text is None:
        return None
    match = DATE_TEXT.fullmatch(text)
    if match is None:
        return None
    day_text, month_text, year_text = match.groups()
    try:
        month = MONTHS.index(month_text.upper()) + 1
        year = datetime.now().year // 100 * 100 + int(year_text)
        return datetime(year, month, int(day_text))
    except (ValueError, IndexError):
        return None


def utc_now_ms() -> datetime:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


def log_msg(store, module: str, message: str) -> Int64 | None:
    """Write an autonomous-transaction-compatible audit message."""
    try:
        counters = store.coll("counters").with_options(write_concern=AUDIT_WRITE_CONCERN)
        seq = counters.find_one_and_update(
            {"_id": SEQ_BILLING_AUDIT_LOG},
            {"$inc": {"seq": Int64(1)}},
            return_document=ReturnDocument.AFTER,
        )
        if seq is None:
            raise LookupError(f"counter {SEQ_BILLING_AUDIT_LOG!r} is not seeded")
        log_id = Int64(seq["seq"])
        doc = {
            "_id": log_id,
            "log_id": log_id,
            "logged_at": utc_now_ms(),
            "module": module[:30] if module is not None else None,
            "message": message[:4000] if message is not None else None,
            "ns": NS_VALUE,
        }
        store.coll("billing_audit_log").with_options(
            write_concern=AUDIT_WRITE_CONCERN
        ).insert_one(doc)
        return log_id
    except PyMongoError:
        return None
