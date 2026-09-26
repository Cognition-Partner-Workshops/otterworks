#!/usr/bin/env python
"""w1-b05 loader: identity lift of audit_events into mmp_rt_billing_n.

fixture mode: reads fx_src_audit_events from mmp_rt_billing_n (MONGODB_MMP_RT_TARGET_N_URI)
live mode:    reads audit_events from mmp_rt_src (MONGODB_MMP_RT_SOURCE_URI, read-only)

Both modes drop and recreate mmp_rt_billing_n.audit_events, copy every document with the
same _id / fields / BSON types, convert string-typed `ts` (M4) to a UTC BSON date, and
recreate the non-_id indexes. Never writes anywhere else.
"""
import argparse
import os
import sys
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import BulkWriteError

TARGET_DB = "mmp_rt_billing_n"
TARGET_URI_SECRET = "MONGODB_MMP_RT_TARGET_N_URI"
SOURCE_URI_SECRET = "MONGODB_MMP_RT_SOURCE_URI"
BATCH_SIZE = 1000
TS_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

UNITS = {
    "audit_events": {
        "indexes": [{"keys": [("ts", 1)], "options": {"name": "ts_1"}}],
    }
}


def uri_from_env(name):
    value = os.environ.get(name)
    if not value:
        sys.exit(f"secret {name} not set in environment")
    return value


def convert_ts(doc):
    ts = doc.get("ts")
    if isinstance(ts, str):
        parsed = datetime.strptime(ts, TS_FORMAT)
        doc["ts"] = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return 1
    if ts is not None and not isinstance(ts, datetime):
        raise TypeError(f"audit_events {doc.get('_id')}: ts has unsupported type {type(ts).__name__}")
    return 0


def load_collection(sourceColl, targetDb, name, spec):
    targetDb.drop_collection(name)
    targetDb.create_collection(name)
    target = targetDb[name]
    inserted = 0
    converted = 0
    batch = []

    def flush():
        nonlocal inserted
        if not batch:
            return
        try:
            result = target.insert_many(batch, ordered=False)
            inserted += len(result.inserted_ids)
        except BulkWriteError as exc:
            raise SystemExit(f"bulk write failed on {name}: {exc.details.get('writeErrors', [])[:1]}")
        batch.clear()

    for doc in sourceColl.find({}, batch_size=BATCH_SIZE):
        if name == "audit_events":
            converted += convert_ts(doc)
        batch.append(doc)
        if len(batch) >= BATCH_SIZE:
            flush()
    flush()

    for idx in spec["indexes"]:
        target.create_index(idx["keys"], **idx["options"])
    return inserted, converted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fixture", "live"], required=True)
    args = parser.parse_args()

    targetClient = MongoClient(uri_from_env(TARGET_URI_SECRET))
    targetDb = targetClient[TARGET_DB]

    if args.mode == "fixture":
        sourceDb = targetDb
        prefix = "fx_src_"
    else:
        sourceDb = MongoClient(uri_from_env(SOURCE_URI_SECRET))["mmp_rt_src"]
        prefix = ""

    for name, spec in UNITS.items():
        sourceColl = sourceDb[prefix + name]
        sourceCount = sourceColl.count_documents({})
        inserted, converted = load_collection(sourceColl, targetDb, name, spec)
        targetCount = targetDb[name].count_documents({})
        stringTs = targetDb[name].count_documents({"ts": {"$type": "string"}})
        nonDateTs = targetDb[name].count_documents({"ts": {"$not": {"$type": "date"}}})
        print(
            f"[{args.mode}] {prefix + name} -> {TARGET_DB}.{name}: "
            f"source={sourceCount} inserted={inserted} target={targetCount} "
            f"ts_converted={converted} target_string_ts={stringTs} target_non_date_ts={nonDateTs}"
        )
        print(f"[{args.mode}] {name} indexes: {targetDb[name].index_information()}")
        if sourceCount != targetCount or nonDateTs != 0:
            sys.exit(f"{name}: count or ts-type check failed")


if __name__ == "__main__":
    main()
