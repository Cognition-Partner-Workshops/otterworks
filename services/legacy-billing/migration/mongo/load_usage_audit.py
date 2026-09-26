"""u-04-usage-audit loader: USAGE_EVENTS -> usageEvents, BILLING_AUDIT_LOG -> billingAuditLog.

Reads the Oracle billing fixture once over a single connection, canonicalizes
per map-draft-2 (mapping.subset.json), and loads exactly the two allowlisted
collections in the target database. Rows that violate the source-side check
semantics (TRG_USAGE_EVENTS_CHECK) or mapping rules are counted per reason and
sampled into the unit report's quarantine_rows; they are never coerced or
silently dropped. Re-running drops and recreates the two collections, so the
load is idempotent.
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import oracledb
from bson.int64 import Int64
from pymongo import MongoClient

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
UNIT = "u-04-usage-audit"
MAX_QUARANTINE_SAMPLES = 100


def _truncate_ms(value):
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def canonicalize_usage_event(row, valid_kinds):
    event_id, tenant_id, occurred_at, units, kind_cd = row
    if event_id is None or (isinstance(event_id, str) and not event_id.strip()):
        return None, "null_key:ID"
    if tenant_id is None:
        return None, "empty_string_is_null:TENANT_ID"
    if isinstance(tenant_id, str) and not tenant_id.strip():
        return None, "empty_string_is_null:TENANT_ID"
    if occurred_at is None:
        return None, "null:OCCURRED_AT"
    if units is None or units <= 0:
        return None, "units_not_positive"
    if kind_cd is None or int(kind_cd) not in valid_kinds:
        return None, "unknown_usage_kind"
    doc = {
        "_id": str(event_id),
        "tenantId": tenant_id,
        "occurredAt": _truncate_ms(occurred_at),
        "units": Int64(int(units)),
        "kindCd": Int64(int(kind_cd)),
    }
    return doc, None


def canonicalize_audit_row(row):
    log_id, logged_at, module, message = row
    if log_id is None:
        return None, "null_key:LOG_ID"
    if logged_at is None:
        return None, "null:LOGGED_AT"
    doc = {"_id": int(log_id), "loggedAt": _truncate_ms(logged_at)}
    if module is not None and str(module).strip():
        doc["module"] = module
    if message is not None and str(message).strip():
        doc["message"] = message
    return doc, None


def _load(rows, canonicalize, collection, reasons, samples):
    docs = []
    seen = set()
    for row in rows:
        doc, reason = canonicalize(row)
        if reason is None and doc["_id"] in seen:
            reason = "duplicate_key"
        if reason is not None:
            reasons[reason] += 1
            if len(samples) < MAX_QUARANTINE_SAMPLES:
                samples.append({"reason": reason, "row": [str(v) for v in row]})
            continue
        seen.add(doc["_id"])
        docs.append(doc)
    if docs:
        collection.insert_many(docs, ordered=True)
    return len(docs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn-secret", required=True)
    parser.add_argument("--target-uri-secret", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--enable-audit-ttl", action="store_true")
    args = parser.parse_args()

    allowlist = json.loads(
        (WORKSPACE_ROOT / ".migration" / "allowed_targets.json").read_text()
    )
    if args.target_db not in allowlist.get("databases", []):
        print(
            json.dumps(
                {
                    "unit": UNIT,
                    "error": f"target database {args.target_db!r} not in allowed_targets databases",
                }
            ),
            file=sys.stderr,
        )
        return 2

    source_dsn = json.loads(os.environ[args.source_dsn_secret])
    target_uri = os.environ[args.target_uri_secret]

    connection = oracledb.connect(
        user=source_dsn["user"],
        password=source_dsn["password"],
        dsn=source_dsn["dsn"],
    )
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT code_val FROM codes WHERE code_type = 'USAGE_KIND'"
        )
        valid_kinds = {int(row[0]) for row in cursor.fetchall()}
        cursor.execute(
            "SELECT id, tenant_id, occurred_at, units, kind_cd "
            "FROM usage_events ORDER BY id"
        )
        usage_rows = cursor.fetchall()
        cursor.execute(
            "SELECT log_id, logged_at, module, message "
            "FROM billing_audit_log ORDER BY log_id"
        )
        audit_rows = cursor.fetchall()
    finally:
        connection.close()

    client = MongoClient(target_uri)
    db = client[args.target_db]
    db.drop_collection("usageEvents")
    db.drop_collection("billingAuditLog")

    db.create_collection(
        "usageEvents",
        validator={
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["_id", "tenantId", "occurredAt", "units", "kindCd"],
                "properties": {
                    "_id": {"bsonType": "string"},
                    "tenantId": {"bsonType": "string"},
                    "occurredAt": {"bsonType": "date"},
                    "units": {"bsonType": "long", "minimum": 1},
                    "kindCd": {"bsonType": "long"},
                },
            }
        },
        validationLevel="strict",
    )
    db.create_collection("billingAuditLog")

    reasons = Counter()
    samples = []
    usage_loaded = _load(
        usage_rows,
        lambda row: canonicalize_usage_event(row, valid_kinds),
        db["usageEvents"],
        reasons,
        samples,
    )
    audit_reasons = Counter()
    audit_samples = []
    audit_loaded = _load(
        audit_rows,
        canonicalize_audit_row,
        db["billingAuditLog"],
        audit_reasons,
        audit_samples,
    )

    indexes = []
    db["usageEvents"].create_index(
        [("tenantId", 1), ("occurredAt", -1)], name="tenantId_1_occurredAt_-1"
    )
    indexes.append("usageEvents:tenantId_1_occurredAt_-1")
    if args.enable_audit_ttl:
        db["billingAuditLog"].create_index(
            "loggedAt",
            name="loggedAt_ttl_90d",
            expireAfterSeconds=90 * 24 * 3600,
        )
        indexes.append("billingAuditLog:loggedAt_ttl_90d")
    else:
        db["billingAuditLog"].create_index("loggedAt", name="loggedAt_1")
        indexes.append("billingAuditLog:loggedAt_1")

    summary = {
        "unit": UNIT,
        "collections": {
            "usageEvents": {
                "source": "USAGE_EVENTS",
                "target": "usageEvents",
                "loaded": usage_loaded,
                "quarantined": sum(reasons.values()),
                "quarantine_reasons": dict(reasons),
            },
            "billingAuditLog": {
                "source": "BILLING_AUDIT_LOG",
                "target": "billingAuditLog",
                "loaded": audit_loaded,
                "quarantined": sum(audit_reasons.values()),
                "quarantine_reasons": dict(audit_reasons),
            },
        },
        "indexes_created": indexes,
        "audit_ttl_enabled": bool(args.enable_audit_ttl),
        "quarantine_rows": samples + audit_samples,
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
