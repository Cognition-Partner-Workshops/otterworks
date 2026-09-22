#!/usr/bin/env python3
"""Mutate exactly one document in a target collection so recon must FAIL.

  python fault_inject.py --collection codes --mode drop-one|alter-field

`drop-one` deletes one doc; `alter-field` changes one non-key field on one
doc. Prints the _id touched (redacted composite keys are printed as their
hash). Mongo URI from MONGO_LOCAL_URI, db ow_billing_offline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

TARGET_DB = "ow_billing_offline"


def _redact(_id):
    return hashlib.sha256(json.dumps(_id, default=str, sort_keys=True).encode()).hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", required=True)
    ap.add_argument("--mode", choices=["drop-one", "alter-field"], required=True)
    args = ap.parse_args()
    if os.environ.get("MONGODB_ATLAS_URI"):
        sys.exit("MONGODB_ATLAS_URI is set: offline mode refuses remote targets")
    uri = os.environ.get("MONGO_LOCAL_URI")
    if not uri:
        sys.exit("MONGO_LOCAL_URI not set")
    from pymongo import MongoClient
    coll = MongoClient(uri)[TARGET_DB][args.collection]
    doc = coll.find_one()
    if doc is None:
        sys.exit(f"{args.collection}: no documents to mutate")
    if args.mode == "drop-one":
        coll.delete_one({"_id": doc["_id"]})
        print(f"dropped {args.collection}._id={_redact(doc['_id'])}")
        return 0
    field = next((k for k in doc if k != "_id"), None)
    if field is None:
        coll.delete_one({"_id": doc["_id"]})
        print(f"dropped {args.collection}._id={_redact(doc['_id'])} (no non-key field to alter)")
        return 0
    coll.update_one({"_id": doc["_id"]}, {"$set": {field: "__fault_injected__"}})
    print(f"altered {args.collection}._id={_redact(doc['_id'])} field {field!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
