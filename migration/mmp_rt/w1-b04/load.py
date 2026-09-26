#!/usr/bin/env python
"""Batch w1-b04 loader: identity lift of `shares` into mmp_rt_billing_n.

Modes:
  fixture  reads fx_src_shares from mmp_rt_billing_n (MONGODB_MMP_RT_TARGET_N_URI)
  live     reads shares from mmp_rt_src (MONGODB_MMP_RT_SOURCE_URI, read-only)

Writes ONLY to mmp_rt_billing_n.shares; the collection is dropped and recreated on every
run so the loader is idempotent. Documents are copied verbatim (same _id, field names and
BSON types). Non-_id indexes are recreated from the source collection with identical
key specs and options (shares has none, but the code path is generic).
Target is a shared M0 free tier: batches of <= 1000, insert_many(ordered=False), one writer.
"""
import argparse
import os
import sys

from pymongo import MongoClient

TARGET_DB = "mmp_rt_billing_n"
SOURCE_DB = "mmp_rt_src"
UNITS = ["shares"]
BATCH = 1000

MODES = {
    "fixture": ("MONGODB_MMP_RT_TARGET_N_URI", TARGET_DB, "fx_src_{}"),
    "live": ("MONGODB_MMP_RT_SOURCE_URI", SOURCE_DB, "{}"),
}


def sourceIndexSpecs(sourceColl):
    specs = []
    for name, info in sourceColl.index_information().items():
        if name == "_id_":
            continue
        options = {k: v for k, v in info.items() if k not in ("key", "v", "ns")}
        options["name"] = name
        specs.append((info["key"], options))
    return specs


def copyCollection(sourceColl, targetColl):
    targetColl.drop()
    inserted = 0
    buf = []
    for doc in sourceColl.find({}, batch_size=BATCH):
        buf.append(doc)
        if len(buf) >= BATCH:
            inserted += len(targetColl.insert_many(buf, ordered=False).inserted_ids)
            buf = []
    if buf:
        inserted += len(targetColl.insert_many(buf, ordered=False).inserted_ids)
    for key, options in sourceIndexSpecs(sourceColl):
        targetColl.create_index(key, **options)
    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=sorted(MODES), required=True)
    args = parser.parse_args()
    sourceSecret, sourceDbName, pattern = MODES[args.mode]

    sourceDb = MongoClient(os.environ[sourceSecret], maxPoolSize=2)[sourceDbName]
    targetDb = MongoClient(os.environ["MONGODB_MMP_RT_TARGET_N_URI"], maxPoolSize=2)[TARGET_DB]

    ok = True
    for unit in UNITS:
        sourceColl = sourceDb[pattern.format(unit)]
        targetColl = targetDb[unit]
        sourceCount = sourceColl.count_documents({})
        inserted = copyCollection(sourceColl, targetColl)
        targetCount = targetColl.count_documents({})
        indexes = sorted(targetColl.index_information())
        print(f"[{args.mode}] {unit}: source={sourceCount} inserted={inserted} "
              f"target={TARGET_DB}.{unit} count={targetCount} indexes={indexes}")
        ok = ok and sourceCount == inserted == targetCount
    if not ok:
        print("COUNT MISMATCH", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
