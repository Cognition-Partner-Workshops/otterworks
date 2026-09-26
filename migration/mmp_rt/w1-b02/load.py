#!/usr/bin/env python
"""w1-b02 loader: identity lift of `documents` into mmp_rt_billing_n.

Modes:
  fixture  read  mmp_rt_billing_n.fx_src_documents (MONGODB_MMP_RT_TARGET_N_URI)
  live     read  mmp_rt_src.documents               (MONGODB_MMP_RT_SOURCE_URI, read-only)

Both modes drop and recreate mmp_rt_billing_n.documents, copy every document
unchanged (raw BSON; Decimal128 `price` and `folderId: null` are preserved as-is),
then recreate the non-_id indexes with identical key spec and options.
"""
import argparse
import json
import os
import sys

from bson.raw_bson import RawBSONDocument
from pymongo import MongoClient

BATCH = "w1-b02"
TARGET_DB = "mmp_rt_billing_n"
UNITS = ["documents"]
BATCH_SIZE = 1000

MODES = {
    "fixture": {"uri_secret": "MONGODB_MMP_RT_TARGET_N_URI", "db": TARGET_DB, "prefix": "fx_src_"},
    "live": {"uri_secret": "MONGODB_MMP_RT_SOURCE_URI", "db": "mmp_rt_src", "prefix": ""},
}


def uriFromSecret(name):
    value = os.environ.get(name)
    if not value:
        sys.exit(f"missing env var {name}")
    return value


def indexSpecs(coll):
    out = []
    for info in coll.list_indexes():
        info = dict(info)
        if info["name"] == "_id_":
            continue
        keys = [(k, v) for k, v in info["key"].items()]
        options = {k: v for k, v in info.items() if k not in ("key", "v", "ns")}
        out.append((keys, options))
    return out


def copyCollection(srcColl, dstDb, name):
    dstDb.drop_collection(name)
    dst = dstDb.get_collection(name, codec_options=srcColl.codec_options)
    copied = 0
    batch = []
    for doc in srcColl.find({}, sort=[("_id", 1)]):
        batch.append(doc)
        if len(batch) >= BATCH_SIZE:
            dst.insert_many(batch, ordered=False)
            copied += len(batch)
            batch = []
    if batch:
        dst.insert_many(batch, ordered=False)
        copied += len(batch)
    for keys, options in indexSpecs(srcColl):
        dst.create_index(keys, **options)
    return copied


def describeIndexes(coll):
    return [
        {k: v for k, v in dict(i).items() if k != "v"}
        for i in coll.list_indexes()
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=sorted(MODES), required=True)
    args = ap.parse_args()
    mode = MODES[args.mode]

    srcClient = MongoClient(uriFromSecret(mode["uri_secret"]), document_class=RawBSONDocument)
    dstClient = MongoClient(uriFromSecret("MONGODB_MMP_RT_TARGET_N_URI"))
    srcDb = srcClient[mode["db"]]
    dstDb = dstClient[TARGET_DB]

    report = {"batch": BATCH, "mode": args.mode, "collections": {}}
    for name in UNITS:
        srcColl = srcDb[mode["prefix"] + name]
        copied = copyCollection(srcColl, dstDb, name)
        report["collections"][name] = {
            "source": f"{mode['db']}.{srcColl.name}",
            "source_count": srcColl.count_documents({}),
            "target": f"{TARGET_DB}.{name}",
            "target_count": dstDb[name].count_documents({}),
            "inserted": copied,
            "source_indexes": describeIndexes(srcColl),
            "target_indexes": describeIndexes(dstDb[name]),
        }
    print(json.dumps(report, indent=2, default=str))
    bad = [n for n, r in report["collections"].items() if r["source_count"] != r["target_count"]]
    if bad:
        sys.exit(f"count mismatch: {bad}")


if __name__ == "__main__":
    main()
