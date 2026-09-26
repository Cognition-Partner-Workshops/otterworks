#!/usr/bin/env python3
"""Unit u-07-plsql-util: PKG_OW_UTIL ported to the MongoDB service model.

Mirrors services/legacy-billing/db/oracle/packages/01_pkg_util.sql:
- f_md5_uuid   -> md5_uuid(): deterministic MD5->UUID key generator
- f_code_desc  -> code_desc(): CODES lookup against the migrated `codes`
                  collection (empty/missing -> 'UNKNOWN(n)')
- f_dt2str     -> dt2str(), f_str2dt -> str2dt(): 'DD-MON-YY' gymnastics;
                  str2dt swallows every parse error and returns None
- log_msg      -> log_msg(): autonomous-transaction audit write into the
                  migrated `billingAuditLog` collection; errors swallowed
- ROUND(x,n)   -> money_round(): Oracle ROUND is half-away-from-zero

BSON rendering helpers (json_value) follow the folded wave-1 feedback:
Decimal128 renders via its Decimal (no normalize() — the facade prints
NUMBER(12,2) with trailing scale, e.g. '49.00'); Int64 renders via str().
"""

from __future__ import annotations

import datetime as _dt
import decimal
import hashlib
from typing import Any

MODULE_MAX = 30
MESSAGE_MAX = 4000


def md5_uuid(s: str) -> str:
    """pkg_ow_util.f_md5_uuid: LOWER(RAWTOHEX(STANDARD_HASH(...,'MD5'))) as uuid."""
    h = hashlib.md5(s.encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def code_desc(db, code_type: str, code_val: int) -> str:
    """pkg_ow_util.f_code_desc over the migrated `codes` collection."""
    doc = db["codes"].find_one(
        {"codeType": code_type, "codeVal": int(code_val)},
        {"codeDesc": 1},
    )
    if doc is None or doc.get("codeDesc") in (None, ""):
        return f"UNKNOWN({code_val if code_val is not None else -1})"
    return doc["codeDesc"]


def _mon(dt: _dt.date) -> str:
    return dt.strftime("%d-%b-%y").upper()


def dt2str(d: _dt.date | _dt.datetime | None) -> str | None:
    """pkg_ow_util.f_dt2str: TO_CHAR(p_dt, 'DD-MON-YY', ENGLISH)."""
    if d is None:
        return None
    return _mon(d)


def str2dt(s: str | None) -> _dt.date | None:
    """pkg_ow_util.f_str2dt: TO_DATE(p_str,'DD-MON-YY'); dirty dates -> NULL."""
    if s is None:
        return None
    try:
        return _dt.datetime.strptime(s.strip().upper(), "%d-%b-%y").date()  # noqa: DTZ007
    except ValueError:
        return None


def money_round(value, places: int = 2):
    """Oracle ROUND: half away from zero. NULL in, NULL out."""
    if value is None:
        return None
    d = value.to_decimal() if hasattr(value, "to_decimal") else decimal.Decimal(str(value))
    return d.quantize(decimal.Decimal(1).scaleb(-places), rounding=decimal.ROUND_HALF_UP)


def log_msg(db, module: str, message: str) -> bool:
    """pkg_ow_util.log_msg: autonomous-commit audit row; failures swallowed.

    Writes one document to `billingAuditLog` per the mapping spec
    (LOG_ID numeric -> _id long; loggedAt real BSON date).
    """
    try:
        coll = db["billingAuditLog"]
        top = coll.find_one(sort=[("_id", -1)], projection={"_id": 1})
        log_id = int(top["_id"]) + 1 if top else 1
        coll.insert_one(
            {
                "_id": log_id,
                "loggedAt": _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None),
                "module": (module or "")[:MODULE_MAX] or None,
                "message": (message or "")[:MESSAGE_MAX] or None,
            }
        )
        return True
    except Exception:  # noqa: BLE001 — pkg_ow_util swallows every error
        return False


def dec2(value: Any) -> str | None:
    """BSON Decimal128 rendered like the recorded transcripts' decimal fields:
    fixed two decimal places ('49.00')."""
    if value is None:
        return None
    d = value.to_decimal() if hasattr(value, "to_decimal") else decimal.Decimal(str(value))
    return f"{d:.2f}"


def json_value(value: Any) -> Any:
    """Render a BSON value the way the Oracle facade serialised it."""
    if hasattr(value, "to_decimal"):  # Decimal128
        return str(value.to_decimal())
    if isinstance(value, _dt.datetime):
        if value.time() == _dt.time.min:
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if hasattr(value, "as_uuid"):  # uuid.UUID
        return str(value)
    return value


def json_row(doc: dict) -> dict:
    return {k: json_value(v) for k, v in doc.items() if k != "_id"}
