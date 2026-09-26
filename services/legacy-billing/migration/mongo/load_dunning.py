"""Loader for unit u-05-dunning-data: DUNNING_ATTEMPTS -> dunningAttempts,
NOTIFICATIONS -> notifications, into Mongo db ow_billing_migration.

Secrets are referenced by environment-variable NAME only; values are never
printed or written to artifacts.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path

UNIT = "u-05-dunning-data"
TARGET_DB = "ow_billing_migration"
WRITE_TARGETS = {
    "dunningAttempts": "DUNNING_ATTEMPTS",
    "notifications": "NOTIFICATIONS",
}
MAPPING_VERSION = "map-draft-2"
TOLERANCE_VERSION = "tol-1"

REPO_ROOT = Path(__file__).resolve().parents[4]


def _fail(message):
    print(message, file=sys.stderr)
    return 2


def _to_long(value):
    if isinstance(value, bool):
        raise TypeError("not an integer value")
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    raise TypeError("not an integer value")


def _to_date(value):
    if isinstance(value, datetime):
        truncated = value.replace(microsecond=value.microsecond // 1000 * 1000)
        return truncated.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    raise TypeError("not a datetime/date")


def _to_string(value):
    if value is None:
        return None
    if value == "":
        return None
    return str(value)


FIELD_SPEC = {
    "dunningAttempts": [
        ("TENANT_ID", "tenantId", _to_string),
        ("INVOICE_ID", "invoiceId", _to_string),
        ("ATTEMPT_NO", "attemptNo", _to_long),
        ("SCHEDULED_FOR", "scheduledFor", _to_date),
        ("STATUS_CD", "statusCd", _to_long),
    ],
    "notifications": [
        ("TENANT_ID", "tenantId", _to_string),
        ("KIND_CD", "kindCd", _to_long),
        ("SENT_AT", "sentAt", _to_date),
    ],
}

REASON_BY_CONVERTER = {
    "_to_long": "bad_numeric",
    "_to_date": "bad_date",
}


def _project_row(collection, row, seen_ids, quarantine):
    key = row["ID"]
    if key is None or str(key) == "":
        quarantine.append({"collection": collection, "source_key": None, "reason": "missing_key"})
        return None
    key = str(key)
    if key in seen_ids:
        quarantine.append({"collection": collection, "source_key": key, "reason": "duplicate_key"})
        return None
    doc = {"_id": key}
    for source, target, convert in FIELD_SPEC[collection]:
        value = row[source]
        try:
            doc[target] = convert(value)
        except (ValueError, TypeError):
            reason = REASON_BY_CONVERTER.get(convert.__name__, "bad_numeric")
            quarantine.append({"collection": collection, "source_key": key, "reason": reason})
            return None
    seen_ids.add(key)
    return doc


def _fetch_source_rows(connection):
    rows = {}
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, tenant_id, invoice_id, attempt_no, scheduled_for, status_cd
                 FROM dunning_attempts ORDER BY id"""
        )
        names = [column[0] for column in cursor.description]
        rows["dunningAttempts"] = [dict(zip(names, row)) for row in cursor]
        cursor.execute(
            """SELECT id, tenant_id, kind_cd, sent_at
                 FROM notifications ORDER BY id"""
        )
        names = [column[0] for column in cursor.description]
        rows["notifications"] = [dict(zip(names, row)) for row in cursor]
    return rows


def _load_once(connection, db):
    source_rows = _fetch_source_rows(connection)
    stats = {}
    quarantine = []
    for collection in WRITE_TARGETS:
        db.drop_collection(collection)
        seen_ids = set()
        docs = []
        for row in source_rows[collection]:
            doc = _project_row(collection, row, seen_ids, quarantine)
            if doc is not None:
                docs.append(doc)
        if docs:
            db[collection].insert_many(docs, ordered=True)
        reasons = {}
        for entry in quarantine:
            if entry["collection"] == collection:
                reasons[entry["reason"]] = reasons.get(entry["reason"], 0) + 1
        stats[collection] = {
            "source_rows": len(source_rows[collection]),
            "loaded": len(docs),
            "quarantined": sum(1 for e in quarantine if e["collection"] == collection),
            "quarantine_reasons": reasons,
        }
    db["dunningAttempts"].create_index([("scheduledFor", -1), ("_id", -1)])
    db["dunningAttempts"].create_index([("invoiceId", 1), ("attemptNo", 1)])
    db["notifications"].create_index([("tenantId", 1), ("kindCd", 1), ("sentAt", 1)])
    snapshot = {
        collection: sorted(str(doc["_id"]) for doc in db[collection].find({}, {"_id": 1}))
        for collection in WRITE_TARGETS
    }
    counts = {collection: db[collection].count_documents({}) for collection in WRITE_TARGETS}
    return stats, quarantine, snapshot, counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn-secret", default="OW_BILLING_FIXTURE_DSN")
    parser.add_argument("--target-uri-secret", default="MONGO_LOCAL_URI")
    parser.add_argument(
        "--allowed-targets-file",
        default=None,
        help="defaults to <repo>/.migration/allowed_targets.json",
    )
    parser.add_argument(
        "--out",
        default=str(
            Path(__file__).resolve().parent / "recon" / UNIT
        ),
    )
    parser.add_argument("--verify-rerun", action="store_true")
    args = parser.parse_args(argv)

    repo_root = REPO_ROOT
    if not (repo_root / ".migration").is_dir():
        return _fail(f"refusal: repo root {repo_root} has no .migration/ directory")
    allowed_file = Path(args.allowed_targets_file) if args.allowed_targets_file else repo_root / ".migration" / "allowed_targets.json"
    try:
        allowed = json.loads(allowed_file.read_text())
    except OSError as exc:
        return _fail(f"refusal: cannot read allowed targets file: {exc}")
    if TARGET_DB not in allowed.get("databases", []):
        return _fail(f"refusal: {TARGET_DB} not in allowed_targets databases")

    source_secret = os.getenv(args.source_dsn_secret)
    if not source_secret:
        return _fail(f"refusal: env var {args.source_dsn_secret} is not set")
    target_uri = os.getenv(args.target_uri_secret)
    if not target_uri:
        return _fail(f"refusal: env var {args.target_uri_secret} is not set")

    try:
        dsn = json.loads(source_secret)
    except json.JSONDecodeError:
        return _fail("refusal: source DSN secret is not valid JSON")

    started = datetime.now(timezone.utc)
    try:
        import oracledb
        import pymongo

        connection = oracledb.connect(
            user=dsn["user"], password=dsn["password"], dsn=dsn["dsn"]
        )
        try:
            client = pymongo.MongoClient(target_uri)
            db = client[TARGET_DB]
            stats, quarantine, snapshot, counts = _load_once(connection, db)
            idempotent = None
            if args.verify_rerun:
                _, quarantine2, snapshot2, counts2 = _load_once(connection, db)
                idempotent = snapshot == snapshot2 and counts == counts2
                quarantine = quarantine2
        finally:
            connection.close()
    except Exception as exc:  # noqa: BLE001 - any driver or load error is exit 1
        print(f"load error: {exc}", file=sys.stderr)
        return 1

    finished = datetime.now(timezone.utc)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "quarantine.json").write_text(json.dumps(quarantine, indent=2) + "\n")
    manifest = {
        "unit": UNIT,
        "target_db": TARGET_DB,
        "write_targets": WRITE_TARGETS,
        "mapping_version": MAPPING_VERSION,
        "tolerance_version": TOLERANCE_VERSION,
        "started": started.isoformat(),
        "finished": finished.isoformat(),
        "collections": stats,
    }
    if args.verify_rerun:
        manifest["idempotent_rerun"] = idempotent
    (out_dir / "load_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for collection, info in stats.items():
        print(
            f"{collection}: source_rows={info['source_rows']} "
            f"loaded={info['loaded']} quarantined={info['quarantined']}"
        )
    if args.verify_rerun:
        print(f"idempotent_rerun={idempotent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
