"""Shared mechanics for the OW_BILLING -> MongoDB unit loaders.

Every loader: reads Oracle through the DSN named by an environment variable (read-only,
one connection), writes only to its declared collections inside the allowlisted database,
drops and recreates those collections at the start of every run (idempotent relaunch),
derives `_id` from the source primary key, and quarantines rows it cannot convert to a
JSON file next to the recon evidence instead of dropping or coercing them.
"""

import json
import os
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import oracledb
from bson.decimal128 import Decimal128
from bson.int64 import Int64
from pymongo import MongoClient

REPO_ROOT = Path(__file__).resolve().parents[4]
ALLOWED_TARGETS_FILE = REPO_ROOT / ".migration" / "allowed_targets.json"


class QuarantineRow(Exception):
    def __init__(self, reason, column, value):
        super().__init__(f"{reason}: {column}")
        self.reason = reason
        self.column = column
        self.value = value


def secret_from_env(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"secret {name} is not set in the environment (pass it by name)")
    return value


def check_allowlist(database):
    allowed = json.loads(ALLOWED_TARGETS_FILE.read_text())["databases"]
    if database not in allowed:
        raise SystemExit(f"target database {database!r} is not in {ALLOWED_TARGETS_FILE}")


def oracle_connection(dsn_secret_name):
    spec = json.loads(secret_from_env(dsn_secret_name))
    return oracledb.connect(user=spec["user"], password=spec["password"], dsn=spec["dsn"])


def fetch_rows(connection, sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        names = [column[0] for column in cursor.description]
        for row in cursor:
            yield dict(zip(names, row))


def target_database(uri_secret_name, database):
    check_allowlist(database)
    client = MongoClient(secret_from_env(uri_secret_name), serverSelectionTimeoutMS=5000)
    return client[database]


def reset_collections(db, names, owned):
    for name in names:
        if name not in owned:
            raise SystemExit(f"{name} is not a declared write target of this unit")
        db.drop_collection(name)
        db.create_collection(name)


def as_string(value, column):
    if value is None:
        return None
    if not isinstance(value, str):
        raise QuarantineRow("bad_type", column, value)
    value = value.rstrip(" ")
    return value if value != "" else None


def as_long(value, column):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise QuarantineRow("bad_type", column, value)
    if isinstance(value, Decimal) and value != value.to_integral_value():
        raise QuarantineRow("non_integral", column, value)
    return Int64(int(value))


def as_decimal(value, column, scale):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, Decimal, float)):
        raise QuarantineRow("bad_type", column, value)
    quantum = Decimal(1).scaleb(-scale)
    return Decimal128(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_EVEN))


def as_bool_yn(value, column):
    if value is None:
        return None
    flag = value.strip().upper() if isinstance(value, str) else value
    if flag == "Y":
        return True
    if flag == "N":
        return False
    raise QuarantineRow("bad_yn", column, value)


def as_utc_datetime(value, column):
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise QuarantineRow("bad_type", column, value)
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def as_datetime_from_text(value, column, fmt):
    if value is None:
        return None
    if not isinstance(value, str):
        raise QuarantineRow("bad_type", column, value)
    text = value.strip()
    if text == "":
        return None
    try:
        return datetime.strptime(text, fmt)  # noqa: DTZ007 naive UTC BSON date
    except ValueError:
        raise QuarantineRow("bad_date", column, value)


def strip_missing(document, optional_fields):
    """null_missing_equiv: nullable fields are omitted rather than stored as null."""
    return {
        key: value
        for key, value in document.items()
        if not (value is None and key in optional_fields)
    }


def write_quarantine(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = {}
    for entry in entries:
        counts[entry["reason"]] = counts.get(entry["reason"], 0) + 1
    path.write_text(
        json.dumps(
            {
                "kind": "quarantine",
                "total": len(entries),
                "by_reason": counts,
                "rows": [
                    {k: v for k, v in entry.items() if k != "value"}
                    for entry in entries
                ],
            },
            indent=1,
            default=str,
        )
        + "\n"
    )
    return counts
