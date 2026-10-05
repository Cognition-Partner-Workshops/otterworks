#!/usr/bin/env python3
"""Prove migration/billing/mapping_spec.json is executable MongoDB: derive a $jsonSchema validator per
collection from the spec, create every collection and index on a scratch database, insert one
synthetic document per collection built from the required fields, and confirm the embedded-array
maxItems bound rejects an oversize array.

Usage:
    check_spec_mongo.py --uri mongodb://127.0.0.1:27117 --db ow_tp_mapping_check

Intended for a throwaway local mongod (e.g. docker run mongo:7). It refuses a URI that is not
loopback unless --allow-remote is given, and never reads MONGODB_ATLAS_URI. The scratch
database is dropped at the end. Output is a plain pass/fail listing for the PR evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from decimal import Decimal
from pathlib import Path

from bson import Decimal128, Int64
from pymongo import ASCENDING, DESCENDING, IndexModel, MongoClient
from pymongo.errors import WriteError

SPEC = Path(__file__).resolve().parents[1] / "mapping_spec.json"

BSON = {"string": "string", "int": "int", "long": "long", "decimal": "decimal", "date": "date",
        "object": "object", "array<string>": "array", "bool | decimal | string": ["bool", "decimal", "string"]}
SAMPLE = {"string": "x", "int": 1, "long": Int64(1), "decimal": Decimal128(Decimal("1.00")), "date": dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
          "object": {"reason": "orphaned_rows"}, "array<string>": ["1"], "bool | decimal | string": True}


def prop(f: dict) -> dict:
    p = {"bsonType": BSON[f["bson"]]}
    if f["bson"] == "array<string>":
        p["items"] = {"bsonType": "string"}
    return p


def schema_for(coll: dict) -> dict:
    props, required = {}, ["_id"]
    for f in coll["fields"]:
        props[f["field"]] = prop(f)
        if not f["nullable"]:
            required.append(f["field"])
    for e in coll["embedded"]:
        sub_props = {f["field"]: prop(f) for f in e["fields"]}
        sub_req = [f["field"] for f in e["fields"] if not f["nullable"]]
        sub = {"bsonType": "object", "properties": sub_props, "required": sub_req, "additionalProperties": False}
        if e["relationship"] == "one-to-one":
            props[e["path"]] = sub
        else:
            props[e["path"]] = {"bsonType": "array", "maxItems": e["bound"]["max_elements"], "items": sub}
    shape = coll["_id"]["shape"]
    if isinstance(shape, dict):
        props["_id"] = {"bsonType": "object", "required": list(shape), "additionalProperties": False,
                        "properties": {k: {"bsonType": BSON[v]} for k, v in shape.items()}}
    else:
        props["_id"] = {"bsonType": BSON[shape]}
    return {"$jsonSchema": {"bsonType": "object", "required": sorted(set(required)), "properties": props, "additionalProperties": False}}


def sample_doc(coll: dict) -> dict:
    shape = coll["_id"]["shape"]
    doc = {"_id": {k: SAMPLE[v] for k, v in shape.items()} if isinstance(shape, dict) else SAMPLE[shape]}
    for f in coll["fields"]:
        if not f["nullable"]:
            doc[f["field"]] = SAMPLE[f["bson"]]
    for e in coll["embedded"]:
        sub = {f["field"]: SAMPLE[f["bson"]] for f in e["fields"] if not f["nullable"]}
        doc[e["path"]] = sub if e["relationship"] == "one-to-one" else [sub]
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", required=True)
    ap.add_argument("--db", default="ow_tp_mapping_check")
    ap.add_argument("--allow-remote", action="store_true")
    args = ap.parse_args()
    if not args.allow_remote and not any(h in args.uri for h in ("127.0.0.1", "localhost")):
        raise SystemExit("refusing a non-loopback URI without --allow-remote (this check is for a scratch mongod)")

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    client = MongoClient(args.uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[args.db]
    client.drop_database(args.db)
    failures = 0
    for coll in spec["collections"]:
        name = coll["name"]
        db.create_collection(name, validator=schema_for(coll), validationLevel="strict", validationAction="error")
        models = []
        for i in coll["indexes"]:
            keys = [(k, ASCENDING if v == 1 else DESCENDING) for k, v in i["keys"].items()]
            opts = {k: v for k, v in i["options"].items() if k != "build"}
            models.append(IndexModel(keys, name=i["name"], **opts))
        created = db[name].create_indexes(models) if models else []
        db[name].insert_one(sample_doc(coll))
        oversize_ok = True
        for e in coll["embedded"]:
            if e["relationship"] == "one-to-one":
                continue
            bad = sample_doc(coll)
            bad["_id"] = "oversize" if not isinstance(bad["_id"], dict) else bad["_id"]
            bad[e["path"]] = bad[e["path"]] * (e["bound"]["max_elements"] + 1)
            try:
                db[name].insert_one(bad)
                oversize_ok = False
            except WriteError:
                pass
        status = "ok" if oversize_ok else "FAIL maxItems not enforced"
        if not oversize_ok:
            failures += 1
        print(f"{status:4} {name:26} indexes={len(created)} {','.join(created) or '-'}")
    client.drop_database(args.db)
    print(f"{'FAIL' if failures else 'OK'} {len(spec['collections'])} collections created with derived $jsonSchema validators, "
          f"{sum(len(c['indexes']) for c in spec['collections'])} indexes built, scratch db {args.db} dropped")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
