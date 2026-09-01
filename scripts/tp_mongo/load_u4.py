#!/usr/bin/env python3
"""U4: load the DynamoDB `otterworks-file-metadata` partition (ns=<source_ns>) into `files`.

Item-per-document 1:1 per mapping spec v1.0 (D1, D2, D8). Read-only against DynamoDB;
writes drop+recreate ONLY the `files` collection of the registered target database.
Orphaned S3 markers (derived_ungraded `orphaned_metadata`) are reported, never dropped.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAPPING_SPEC = REPO_ROOT / ".migration/03_mapping_spec.json"
UNIT = "U4"
COLLECTION = "files"
FILES_BUCKET = "otterworks-files"
INSERT_BATCH = 1000


def _secret(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"secret '{name}' not found in environment; pass secrets by name only")
    return value


def _aws(kind: str, service: str):
    import boto3

    factory = boto3.resource if kind == "resource" else boto3.client
    return factory(
        service,
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )


def to_string(v):
    return None if v is None else str(v)


def to_int(v):
    return None if v is None else int(Decimal(str(v)))


def to_bool(v):
    if v is None:
        return None
    if not isinstance(v, bool):
        raise TypeError(f"expected BOOL, got {type(v).__name__}")
    return v


def iso_to_date_ms(v):
    """ISO-8601 string -> naive UTC datetime truncated to milliseconds (BSON date)."""
    if v is None:
        return None
    dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)


def converter(field: dict):
    pair = (field["source_type"], field["bson_type"])
    table = {
        ("S", "string"): to_string,
        ("N", "long"): to_int,
        ("N", "int"): to_int,
        ("BOOL", "bool"): to_bool,
        ("S(iso8601)", "date"): iso_to_date_ms,
    }
    if pair not in table:
        raise RuntimeError(f"{field['source']}: unsupported mapping pair {pair[0]} -> {pair[1]}")
    return table[pair]


def load_entry() -> dict:
    spec = json.loads(MAPPING_SPEC.read_text())
    entries = [c for c in spec["collections"] if c["collection"] == COLLECTION]
    if len(entries) != 1 or entries[0]["unit"] != UNIT:
        raise RuntimeError(f"mapping spec does not assign '{COLLECTION}' to {UNIT}")
    entry = entries[0]
    if entry["embeds"]:
        raise RuntimeError("U4 has no embeds by contract")
    return {"spec_version": spec["version"], "entry": entry}


def scan_items(table_name: str, source_ns: str):
    table = _aws("resource", "dynamodb").Table(table_name)
    kwargs = {
        "FilterExpression": "#n = :ns",
        "ExpressionAttributeNames": {"#n": "ns"},
        "ExpressionAttributeValues": {":ns": source_ns},
        "ConsistentRead": True,
    }
    while True:
        resp = table.scan(**kwargs)
        yield from resp.get("Items", [])
        if "LastEvaluatedKey" not in resp:
            return
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def s3_probe_available(source_ns: str) -> bool:
    """True when the files bucket holds objects for this partition, i.e. a HEAD probe is
    informative. The fixture estate stores metadata only, so this is normally False."""
    s3 = _aws("client", "s3")
    try:
        resp = s3.list_objects_v2(Bucket=FILES_BUCKET, Prefix=f"{source_ns}/", MaxKeys=1)
        return resp.get("KeyCount", 0) > 0
    except (s3.exceptions.NoSuchBucket, s3.exceptions.ClientError):
        return False


def orphan_marker(s3_key: str | None, s3_client) -> bool:
    if s3_key is None:
        return True
    if s3_client is None:
        # Estate storage-key convention: objects that were never uploaded live under the
        # `<ns>/missing/` prefix (same rule the legacy fixture validator applies).
        return "/missing/" in s3_key
    try:
        s3_client.head_object(Bucket=FILES_BUCKET, Key=s3_key)
        return False
    except s3_client.exceptions.ClientError:
        return True


def build_document(item: dict, plan: dict, ns_value: str, s3_client) -> dict:
    doc = {}
    for field in plan["fields"]:
        doc[field["target"]] = field["convert"](item.get(field["source"]))
    doc["ns"] = ns_value
    doc["orphaned_metadata"] = orphan_marker(item.get("s3_key"), s3_client)
    return doc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--uri-secret", default="MONGODB_ATLAS_URI")
    p.add_argument("--target-db", default=None)
    p.add_argument("--source-ns", default="demo")
    p.add_argument("--report", type=Path, default=REPO_ROOT / ".migration/recon/U4/load_report.json")
    args = p.parse_args()

    from pymongo import ASCENDING, MongoClient

    loaded = load_entry()
    entry = loaded["entry"]
    target_db = args.target_db or json.loads(MAPPING_SPEC.read_text())["target_database"]
    ns_value = entry["namespace_field"]["value"]
    if entry["namespace_field"]["target"] != "ns":
        raise RuntimeError("namespace field must be `ns` (D8)")
    if entry["root_where"] != "ns = '${source_ns}'":
        raise RuntimeError(f"unexpected root_where {entry['root_where']!r}")
    plan = {
        "fields": [
            {"source": f["source"], "target": f["target"], "convert": converter(f)}
            for f in entry["fields"]
        ]
    }
    if entry["key"]["source"] != ["id"] or entry["key"]["target"] != "_id":
        raise RuntimeError("U4 key must be id -> _id (D1)")

    started = datetime.now(timezone.utc)
    s3_client = _aws("client", "s3") if s3_probe_available(args.source_ns) else None

    client = MongoClient(_secret(args.uri_secret))
    db = client[target_db]
    existed_before = COLLECTION in db.list_collection_names()
    docs_before = db[COLLECTION].estimated_document_count() if existed_before else 0
    db[COLLECTION].drop()  # ONLY U4's collection

    coll = db[COLLECTION]
    batch, inserted, scanned, orphans = [], 0, 0, 0
    for item in scan_items(entry["root_table"], args.source_ns):
        scanned += 1
        doc = build_document(item, plan, ns_value, s3_client)
        orphans += int(doc["orphaned_metadata"])
        batch.append(doc)
        if len(batch) >= INSERT_BATCH:
            inserted += len(coll.insert_many(batch, ordered=True).inserted_ids)
            batch = []
    if batch:
        inserted += len(coll.insert_many(batch, ordered=True).inserted_ids)

    index_names = []
    for idx in entry["indexes"]:
        keys = [(k, ASCENDING if v == 1 else v) for k, v in idx["keys"].items()]
        index_names.append(coll.create_index(keys))

    report = {
        "unit": UNIT,
        "collection": f"{target_db}.{COLLECTION}",
        "mapping_version": loaded["spec_version"],
        "source": {
            "table": entry["root_table"],
            "root_where": entry["root_where"],
            "source_ns": args.source_ns,
            "endpoint": os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
        },
        "ns": ns_value,
        "run_mode": "fixture",
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "idempotency": {
            "strategy": "drop+recreate files only",
            "collection_existed_before": existed_before,
            "docs_before_drop": docs_before,
        },
        "items_scanned": scanned,
        "docs_inserted": inserted,
        "docs_in_collection": coll.count_documents({}),
        "indexes": index_names,
        "orphaned_metadata": {
            "count": orphans,
            "detection": "s3_head_object" if s3_client else "s3_key_convention:/missing/",
            "disposition": "reported; items migrated",
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("docs_inserted", "docs_in_collection", "orphaned_metadata", "indexes")}))
    return 0 if inserted == scanned else 1


if __name__ == "__main__":
    sys.exit(main())
