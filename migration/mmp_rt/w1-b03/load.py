#!/usr/bin/env python3
"""Batch w1-b03 loader: identity lift of `comments` into mmp_rt_billing_n.

  --mode fixture : read mmp_rt_billing_n.fx_src_comments (MONGODB_MMP_RT_TARGET_N_URI)
  --mode live    : read mmp_rt_src.comments            (MONGODB_MMP_RT_SOURCE_URI, read-only)

Write targets (dropped and recreated on every run):
  mmp_rt_billing_n.comments
  mmp_rt_billing_n._dq_comments_orphans   (M1 work-list: comments whose documentId
                                           matches no <source>.documents._id)
"""
import argparse
import datetime as dt
import os
import sys

from pymongo import ASCENDING, MongoClient

TARGET_DB = "mmp_rt_billing_n"
COLLECTION = "comments"
ORPHANS = "_dq_comments_orphans"
BATCH = 1000
INDEXES = [{"key": [("documentId", ASCENDING)], "name": "documentId_1"}]

MODES = {
    "fixture": {"uri_env": "MONGODB_MMP_RT_TARGET_N_URI", "db": TARGET_DB, "prefix": "fx_src_"},
    "live": {"uri_env": "MONGODB_MMP_RT_SOURCE_URI", "db": "mmp_rt_src", "prefix": ""},
}


def batches(cursor, size):
    buf = []
    for doc in cursor:
        buf.append(doc)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=MODES, required=True)
    args = ap.parse_args()
    cfg = MODES[args.mode]

    srcUri = os.environ.get(cfg["uri_env"])
    tgtUri = os.environ.get("MONGODB_MMP_RT_TARGET_N_URI")
    if not srcUri or not tgtUri:
        sys.exit(f"missing env {cfg['uri_env']} and/or MONGODB_MMP_RT_TARGET_N_URI")

    srcDb = MongoClient(srcUri)[cfg["db"]]
    tgtDb = MongoClient(tgtUri)[TARGET_DB]
    srcComments = srcDb[cfg["prefix"] + COLLECTION]
    srcDocuments = srcDb[cfg["prefix"] + "documents"]
    tgtComments = tgtDb[COLLECTION]
    tgtOrphans = tgtDb[ORPHANS]

    tgtComments.drop()
    tgtOrphans.drop()

    inserted = 0
    for chunk in batches(srcComments.find({}), BATCH):
        inserted += len(tgtComments.insert_many(chunk, ordered=False).inserted_ids)

    for spec in INDEXES:
        tgtComments.create_index(spec["key"], name=spec["name"])

    # M1: orphan documentId work-list, computed from the source side only.
    documentIds = set(d["_id"] for d in srcDocuments.find({}, {"_id": 1}))
    now = dt.datetime.now(dt.timezone.utc)
    orphanDocs = [
        {"_id": c["_id"], "documentId": c.get("documentId"), "reason": "orphan_documentId", "detectedAt": now}
        for c in srcComments.find({}, {"_id": 1, "documentId": 1})
        if c.get("documentId") not in documentIds
    ]
    for chunk in batches(iter(orphanDocs), BATCH):
        tgtOrphans.insert_many(chunk, ordered=False)

    print(f"mode={args.mode} source={cfg['db']}.{cfg['prefix']}{COLLECTION} source_count={srcComments.count_documents({})}")
    print(f"inserted={inserted} target_count={tgtComments.count_documents({})}")
    print(f"source_documents={len(documentIds)} orphans={tgtOrphans.count_documents({})}")
    print(f"target_indexes={[i['name'] for i in tgtComments.list_indexes()]}")


if __name__ == "__main__":
    main()
