"""Load one migration unit from Oracle into the migration database.

Driven entirely by .migration/03_mapping_spec.json, so the thing that is loaded and the
thing that recon grades cannot drift: one spec, one set of target paths. There is no
per-unit loader.

Properties this relies on being true:

* Source access is SELECT only. The only statements this issues are SELECTs.
* Idempotent: documents are written with replace_one(upsert=True) keyed on the natural
  `_id`, so a rerun converges instead of duplicating. Reruns after a partial load are
  therefore safe, which is what the rerun budget in the tolerance record assumes.
* One Oracle query in flight at a time (STOP A source-load cap): the root query is drained
  into memory, then one query per embed. Unit-level concurrency is governed separately by
  the extract lease in 04_progress.md.
* Writes land only in --target-db, and only in collections this unit registered.

Usage:
    load_unit.py --unit reference --target-db ow_tp_mongodb_orc1 --param batch_no=85559852
    load_unit.py --unit reference ... --dry-run     # build documents, write nothing
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys

import oracledb
from bson.decimal128 import Decimal128
from pymongo import MongoClient, ReplaceOne

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "03_mapping_spec.json"

# Exact numerics all the way through: without this oracledb hands back a float for
# NUMBER(14,2) and the Decimal128 written to Mongo would carry the float's artifacts.
oracledb.defaults.fetch_decimals = True

MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
DD_MON_YY = re.compile(r"^\s*(\d{1,2})-([A-Za-z]{3})-(\d{2})\s*$")
CSV_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]+$")


class TransformError(ValueError):
    """A value the transform cannot honour. The row is quarantined with its raw value; it
    is never coerced to a plausible-looking substitute."""


# --------------------------------------------------------------------------- transforms
def parse_dd_mon_yy(value):
    """Legacy DD-MON-YY text date. The two-digit year uses the same 1950 pivot the estate's
    NLS settings imply, so 49 -> 2049 and 50 -> 1950."""
    if value is None:
        return None
    m = DD_MON_YY.match(value)
    if not m:
        raise TransformError(f"not DD-MON-YY: {value!r}")
    day, mon, yy = int(m.group(1)), m.group(2).upper(), int(m.group(3))
    if mon not in MONTHS:
        raise TransformError(f"unknown month: {value!r}")
    year = 2000 + yy if yy < 50 else 1900 + yy
    try:
        # Oracle session timezone is UTC per the v1 tolerances, so the parsed date is
        # anchored explicitly rather than left naive.
        return dt.datetime(year, MONTHS[mon], day, tzinfo=dt.UTC)
    except ValueError as exc:
        raise TransformError(f"impossible date: {value!r}") from exc


def csv_to_array(value):
    if value is None:
        return None
    parts = [p.strip() for p in value.split(",")]
    if any(not p or not CSV_TOKEN.match(p) for p in parts):
        raise TransformError(f"malformed CSV: {value!r}")
    return parts


def yn_to_bool(value):
    if value is None:
        return None
    v = value.strip().upper()
    if v not in ("Y", "N"):
        raise TransformError(f"not Y/N: {value!r}")
    return v == "Y"


TRANSFORMS = {"parse_dd_mon_yy": parse_dd_mon_yy, "csv_to_array": csv_to_array,
              "yn_to_bool": yn_to_bool}


# --------------------------------------------------------------------------- bson coercion
def to_bson(value, bson_type):
    if value is None:
        return None
    if bson_type == "decimal128":
        return Decimal128(value if hasattr(value, "as_tuple") else str(value))
    if bson_type == "long":
        return int(value)
    if bson_type == "string":
        # Oracle CHAR is blank-padded; tolerance v1 strips the padding and treats the
        # resulting empty string as the absent value Oracle already considers it to be.
        s = value.rstrip(" ") if isinstance(value, str) else value
        return s or None
    return value


def set_path(doc, path, value):
    """Write a dotted target path, creating intermediate subdocuments. A None value writes
    nothing: tolerance v1 makes an absent field and a NULL equivalent, and omitting keeps
    the 113 unused columns from reappearing as a wall of nulls."""
    if value is None:
        return
    parts = path.split(".")
    for p in parts[:-1]:
        doc = doc.setdefault(p, {})
    doc[parts[-1]] = value


# --------------------------------------------------------------------------- source reads
def substitute(text, params):
    if text is None:
        return None
    def repl(m):
        if m.group(1) not in params:
            sys.exit(f"unresolved placeholder ${{{m.group(1)}}}; pass --param {m.group(1)}=<value>")
        return str(params[m.group(1)])
    return re.sub(r"\$\{(\w+)\}", repl, text)


def select(cur, table, columns, where):
    cols = ", ".join(f'"{c}"' for c in dict.fromkeys(columns))
    cur.execute(f"SELECT {cols} FROM {table}" + (f" WHERE {where}" if where else ""))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur]


def source_columns(block):
    cols = [f["source"] for f in block.get("fields", [])]
    cols += [d["source"] for d in block.get("derived_fields", []) if "source" in d]
    return cols


def build_element(row, embed, code_desc, quarantine):
    el = {}
    set_path(el, embed["key"]["target"], row[embed["key"]["source"][0]])
    apply_block(row, embed, el, code_desc, quarantine)
    return el


def apply_block(row, block, doc, code_desc, quarantine):
    """Raw graded fields first, then the derived values. A failed transform quarantines the
    reason and leaves the derived field absent; the raw value still lands, so the record is
    never lost and recon still grades the source column."""
    for f in block.get("fields", []):
        set_path(doc, f["target"], to_bson(row[f["source"]], f["bson_type"]))
    for d in block.get("derived_fields", []):
        if d["transform"] == "lookup_code_desc":
            code = row.get(d["source"])
            if code is None:
                continue
            label = code_desc.get((d["code_type"], str(int(code))))
            if label is None:
                # A code outside the CODES domain is a source-data finding, not a value to
                # drop: omitting it silently would ship a document that looks complete.
                raise SystemExit(f"{d['source']}={code} has no {d['code_type']} row in "
                                 "CODES; halt and record the finding rather than loading a "
                                 "document with a missing label")
            set_path(doc, d["target"], label)
            continue
        try:
            set_path(doc, d["target"], TRANSFORMS[d["transform"]](row[d["source"]]))
        except TransformError as exc:
            quarantine.append({"source_column": d["source"], "raw_value": row[d["source"]],
                               "target_field": d["target"], "reason": str(exc)})


# --------------------------------------------------------------------------- load
def load_collection(cur, db, coll_spec, params, code_desc, dry_run):
    name = coll_spec["collection"]
    root_where = substitute(coll_spec.get("root_where"), params)
    key = coll_spec["key"]
    compose = key.get("compose")
    key_cols = compose["from"] if compose else key["source"]

    rows = select(cur, coll_spec["root_table"], key_cols + source_columns(coll_spec), root_where)

    # One query per embed, drained before the next: the source-load cap is 1.
    children: dict[str, dict[tuple, list]] = {}
    for e in coll_spec.get("embeds", []):
        grouped: dict[tuple, list] = {}
        for r in select(cur, e["child_table"],
                        e["parent_key"] + e["key"]["source"] + source_columns(e),
                        substitute(e.get("child_where"), params)):
            grouped.setdefault(tuple(r[k] for k in e["parent_key"]), []).append(r)
        children[e["array_path"]] = grouped

    docs, quarantined = [], []
    for row in rows:
        if compose:
            _id = compose["sep"].join(str(row[c]) for c in compose["from"])
        else:
            _id = to_bson(row[key_cols[0]], "string" if isinstance(row[key_cols[0]], str) else "")
        q: list[dict] = []
        doc = {}
        apply_block(row, coll_spec, doc, code_desc, q)
        doc[key["target"]] = _id
        for e in coll_spec.get("embeds", []):
            kids = children[e["array_path"]].get(tuple(row[c] for c in e["parent_key"]), [])
            elems = [build_element(k, e, code_desc, q) for k in kids]
            if elems:
                doc[e["array_path"]] = elems
        for entry in q:
            quarantined.append({"_id": f"{name}:{_id}:{entry['source_column']}",
                                "collection": name, "document_id": _id, **entry})
        docs.append(doc)

    orphans = []
    for e in coll_spec.get("embeds", []):
        parents = {tuple(row[c] for c in e["parent_key"]) for row in rows}
        for pk, kids in children[e["array_path"]].items():
            if pk not in parents:
                orphans += [{"_id": f"{name}:orphan:{e['child_table']}:{k[e['key']['source'][0]]}",
                             "collection": name, "reason": "orphan child row: no root row for "
                             f"parent key {pk}", "child_table": e["child_table"],
                             "raw_row": {kk: str(vv) for kk, vv in k.items()}} for k in kids]

    summary = {"collection": name, "documents": len(docs),
               "embedded": {e["array_path"]: sum(len(d.get(e["array_path"], []))
                                                 for d in docs)
                            for e in coll_spec.get("embeds", [])},
               "quarantined": len(quarantined) + len(orphans)}
    if dry_run:
        return summary, docs[:1]

    # An empty source still materializes its collection: a downstream count check must see a
    # real zero rather than an absent collection it could read as "not loaded yet".
    if name not in db.list_collection_names():
        db.create_collection(name)
    if docs:
        db[name].bulk_write([ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs],
                            ordered=False)
    qcoll = (coll_spec.get("quarantine") or {}).get("collection")
    if qcoll:
        if qcoll not in db.list_collection_names():
            db.create_collection(qcoll)
        if quarantined or orphans:
            db[qcoll].bulk_write([ReplaceOne({"_id": d["_id"]}, d, upsert=True)
                                  for d in quarantined + orphans], ordered=False)
    for spec_index in coll_spec.get("indexes", []):
        kwargs = {k: v for k, v in spec_index.items() if k in ("unique", "collation",
                                                               "expireAfterSeconds")}
        db[name].create_index(list(spec_index["keys"].items()), **kwargs)
    return summary, docs[:1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", required=True)
    ap.add_argument("--target-db", required=True)
    ap.add_argument("--source-dsn-secret", default="OW_ORACLE_BILLING_DSN")
    ap.add_argument("--target-uri-secret", default="MONGODB_ATLAS_URI")
    ap.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    params = dict(p.split("=", 1) for p in args.param)
    spec = json.loads(SPEC_PATH.read_text())
    colls = [c for c in spec["collections"] if c.get("unit") == args.unit]
    if not colls:
        sys.exit(f"no collections for unit '{args.unit}' in {SPEC_PATH}")

    dsn = os.environ.get(args.source_dsn_secret)
    if not dsn:
        sys.exit(f"secret '{args.source_dsn_secret}' not in environment; secrets by name only")
    user, password, conn_str = dsn.split("/", 2)

    client = None if args.dry_run else MongoClient(os.environ["MONGODB_ATLAS_URI"])
    db = None if args.dry_run else client[args.target_db]

    with (oracledb.connect(user=user, password=password, dsn=conn_str) as con,
          con.cursor() as cur):
        # CODES is loaded first in wave 0, so the label denormalization every later unit
        # depends on reads it straight from the source rather than from the target.
        code_desc = {(r["CODE_TYPE"], str(r["CODE_VAL"])): r["CODE_DESC"]
                     for r in select(cur, "CODES", ["CODE_TYPE", "CODE_VAL", "CODE_DESC"], None)}
        report = {"unit": args.unit, "mapping_version": spec["version"],
                  "target_db": args.target_db, "dry_run": args.dry_run,
                  "params": params, "collections": []}
        for c in colls:
            summary, sample = load_collection(cur, db, c, params, code_desc, args.dry_run)
            expected = c["expected_documents"]
            summary["expected_documents"] = expected
            summary["matches_census"] = summary["documents"] == expected
            report["collections"].append(summary)
            print(json.dumps(summary))
            if args.dry_run and sample:
                print(json.dumps(sample[0], indent=2, default=str))
    if not all(c["matches_census"] for c in report["collections"]):
        sys.exit("loaded document count does not match the census; not proceeding to recon")


if __name__ == "__main__":
    main()
