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
import contextlib
import copy
import datetime as dt
import decimal
import fcntl
import hashlib
import json
import os
import pathlib
import re
import sys

import oracledb
from bson.decimal128 import Decimal128
from bson.int64 import Int64
from pymongo import MongoClient, ReplaceOne

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "03_mapping_spec.json"
CONVENTIONS_PATH = ROOT / "01_conventions.md"
EXTRACT_LOCK_PATH = ROOT / ".extract.lock"

# Run parameters are interpolated into SQL text (an Oracle bind cannot appear in every
# position a scope predicate needs), so the value space is restricted to what a scope
# parameter legitimately is. Anything else would be a way to widen the extract.
PARAM_VALUE = re.compile(r"^[A-Za-z0-9_.:-]+$")

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
def to_bson(value, bson_type, rules=()):
    if value is None:
        return None
    if bson_type == "decimal128":
        return Decimal128(value if hasattr(value, "as_tuple") else str(value))
    if bson_type == "long":
        # Int64, not int: pymongo encodes a small Python int as int32, which is not the type
        # the mapping declares and not the type the target's validator accepts.
        return Int64(value)
    if bson_type == "string":
        # Blank padding is stripped only where the mapping says so -- that rule is attached
        # to CHAR, which Oracle pads, and recon canonicalizes both sides the same way. A
        # VARCHAR2 stays byte-exact: its trailing spaces are data the source chose to store,
        # and stripping them turns ' - - ' into a value that no longer matches the source.
        if isinstance(value, str) and "rstrip_spaces" in rules:
            return value.rstrip(" ") or None
        return value
    return value


def key_to_bson(value, what):
    """Coerce an identifier to the BSON type tolerance v1 gives it. Oracle hands back every
    NUMBER as a Decimal, and a Decimal is not BSON-encodable, so an unconverted key aborts
    the write rather than storing a wrong type -- but a key with a fractional part is a
    modelling error, not something to round into an _id."""
    if isinstance(value, str):
        return value
    if isinstance(value, decimal.Decimal):
        if value != value.to_integral_value():
            sys.exit(f"{what} is {value}, which is not integer-safe; a key must not carry a "
                     "fractional part")
        return Int64(value)
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
def designated_database():
    """The one database this run may write to, read from 01_conventions.md so the guard and
    the record cannot drift. Anything else -- including the two existing demo databases on
    the same cluster -- is out of bounds for this loader."""
    m = re.search(r"^\|\s*Migration database\s*\|\s*`([^`]+)`", CONVENTIONS_PATH.read_text(),
                  re.MULTILINE)
    if not m:
        sys.exit(f"no 'Migration database' row in {CONVENTIONS_PATH}; refusing to guess a "
                 "write target")
    return m.group(1)


@contextlib.contextmanager
def extract_lease(path=EXTRACT_LOCK_PATH):
    """Hold the source-load cap of 1 for the whole extract phase. The ledger row in
    04_progress.md is a record of who holds it; this is the thing that makes a second
    concurrent loader wait, since a wave runs three units wide and two of them read enough
    rows to contend. flock releases on close, so a crashed loader cannot strand the lease."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print(f"waiting for the Oracle extract lease held by another loader ({path})",
                  file=sys.stderr)
            fcntl.flock(fh, fcntl.LOCK_EX)
        fh.write(f"{os.getpid()}\n")
        fh.flush()
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


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
    src = embed["key"]["source"][0]
    set_path(el, embed["key"]["target"], key_to_bson(row[src], f"{embed['child_table']}.{src}"))
    apply_block(row, embed, el, code_desc, quarantine)
    return el


def apply_block(row, block, doc, code_desc, quarantine):
    """Raw graded fields first, then the derived values. A failed transform quarantines the
    reason and leaves the derived field absent; the raw value still lands, so the record is
    never lost and recon still grades the source column."""
    for f in block.get("fields", []):
        set_path(doc, f["target"], to_bson(row[f["source"]], f["bson_type"], f.get("rules", ())))
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
                               "target_field": d["target"], "reason": str(exc),
                               "category": d["quarantine_category"]})


# --------------------------------------------------------------------------- load
def anomaly_mismatches(coll_spec, actual):
    """The mapping declares how many of each known source anomaly this unit must surface.
    A load that quarantines fewer has silently dropped or repaired something; one that
    quarantines more has found an anomaly nobody signed off on. Both stop the unit here,
    before recon, rather than being retyped by hand into the recon report later."""
    expected = (coll_spec.get("quarantine") or {}).get("expected", {})
    out = []
    for category, want in expected.items():
        got = actual.get(category, 0)
        if got != want:
            out.append(f"{coll_spec['collection']}.{category}: expected {want}, got {got}")
    for category, got in actual.items():
        if category not in expected:
            out.append(f"{coll_spec['collection']}.{category}: {got} quarantined but the "
                       "mapping declares no such anomaly")
    return out


def content_digest(docs):
    """A digest of the documents this load would publish. Equal counts do not prove equal
    content, so the rerun comparison that grades idempotency needs the content itself; the
    documents are hashed in key order so the digest does not depend on extract order."""
    h = hashlib.sha256()
    for d in sorted(docs, key=lambda d: str(d["_id"])):
        h.update(json.dumps(d, sort_keys=True, default=str).encode())
        h.update(b"\0")
    return h.hexdigest()


def install_validator(db, coll_spec, code_desc):
    """Install the collection's declared $jsonSchema before its documents are written. The
    Oracle trigger these replace rejected the offending INSERT, so the target has to reject
    it too: a validator installed after the load would leave the invariant unenforced for
    exactly the rows the migration itself wrote."""
    validator = coll_spec.get("validator")
    if not validator:
        return
    validator = copy.deepcopy(validator)
    # A trigger could query CODES; $jsonSchema cannot cross collections, so the reference
    # set is resolved to an enum here, from the same source rows the labels come from.
    for field, code_type in (coll_spec.get("validator_enum_from_codes") or {}).items():
        allowed = sorted(int(v) for (t, v) in code_desc if t == code_type)
        if not allowed:
            sys.exit(f"{coll_spec['collection']}.{field}: CODES has no '{code_type}' rows, so "
                     "the validator would accept every value the trigger rejected")
        validator["$jsonSchema"]["properties"][field]["enum"] = allowed
    db.command("collMod", coll_spec["collection"], validator=validator,
               validationLevel="strict", validationAction="error")


def scope_of(coll_spec, params, docs):
    """The part of the collection this extract owns, as a Mongo filter.

    A `root_where` carrying a run parameter means the extract is one slice of a collection
    that holds several -- `invoices` is loaded a batch at a time -- so the documents outside
    the slice are another batch's live data, not stale rows. Pruning has to be confined to
    the slice, and the loader refuses to guess where it ends: a scoped collection that does
    not declare its scope stops the load, and an extract that returned a row from outside
    the declared scope stops it too, since the filter would then delete live documents.

    An unscoped collection returns an empty filter: its extract is the whole collection.
    """
    where = coll_spec.get("root_where")
    scope = coll_spec.get("scope")
    if not where or "${" not in where:
        return {}
    if not scope:
        sys.exit(f"{coll_spec['collection']}: root_where {where!r} scopes the extract to one "
                 "slice of the collection, but the mapping declares no scope; the loader "
                 "cannot tell another slice's documents from stale ones")
    field = scope["target_field"]
    declared = [f for f in coll_spec.get("fields", []) if f["source"] == scope["source_column"]]
    if not declared:
        sys.exit(f"{coll_spec['collection']}: scope column {scope['source_column']} is not a "
                 "graded field, so the scope cannot be identified in the target")
    raw = params[scope["param"]]
    bson_type = declared[0]["bson_type"]
    value = to_bson(decimal.Decimal(raw) if bson_type in ("long", "decimal128") else raw,
                    bson_type)
    stray = {get_path(d, field) for d in docs} - {value}
    if stray:
        sys.exit(f"{coll_spec['collection']}: the extract returned {field} values outside the "
                 f"declared scope {value} ({sorted(map(str, stray))}); the scope filter would "
                 "delete live documents")
    return {field: value}


def get_path(doc, path):
    for part in path.split("."):
        doc = (doc or {}).get(part)
    return doc


def load_collection(cur, db, coll_spec, params, code_desc, dry_run):
    name = coll_spec["collection"]
    root_where = substitute(coll_spec.get("root_where"), params)
    key = coll_spec["key"]
    compose = key.get("compose")
    key_cols = compose["from"] if compose else key["source"]

    rows = select(cur, coll_spec["root_table"], key_cols + source_columns(coll_spec), root_where)

    # `parent_key` names columns on the CHILD table whose values join to the root key --
    # the two sides are named differently (ENTITY_ATTR_VALUE.ENTITY_ID -> CUSTOMER_MASTER
    # .CUST_ID), so the child is grouped by parent_key and looked up by the root key.
    # One query per embed, drained before the next: the source-load cap is 1.
    children: dict[str, dict[tuple, list]] = {}
    for e in coll_spec.get("embeds", []):
        if len(e["parent_key"]) != len(key_cols):
            sys.exit(f"{name}.{e['array_path']}: parent_key {e['parent_key']} does not have "
                     f"the arity of the root key {key_cols}; the embed cannot be joined")
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
            _id = key_to_bson(row[key_cols[0]], f"{coll_spec['root_table']}.{key_cols[0]}")
        q: list[dict] = []
        doc = {}
        apply_block(row, coll_spec, doc, code_desc, q)
        doc[key["target"]] = _id
        for e in coll_spec.get("embeds", []):
            kids = children[e["array_path"]].get(tuple(row[c] for c in key_cols), [])
            elems = [build_element(k, e, code_desc, q) for k in kids]
            if elems:
                doc[e["array_path"]] = elems
        for entry in q:
            quarantined.append({"_id": f"{name}:{_id}:{entry['source_column']}",
                                "collection": name, "document_id": _id, **entry})
        docs.append(doc)

    # Orphans are found two ways, and both are needed. An embed's `child_where` may itself
    # exclude parentless rows (it has to: the graded array must contain exactly the children
    # the harness counts on the source side), so a separate `orphan_where` pass goes back for
    # the rows that predicate hides -- otherwise the anomaly would simply never be extracted
    # and would look like clean data. The set difference below still catches anything the
    # predicate let through.
    orphans = []
    parents = {tuple(row[c] for c in key_cols) for row in rows}
    for e in coll_spec.get("embeds", []):
        def orphan_docs(kids, pk, e=e):
            if not e.get("orphan_category"):
                sys.exit(f"{name}.{e['array_path']}: parentless {e['child_table']} rows exist "
                         "but the mapping declares no orphan_category for them; the anomaly "
                         "has to be named and counted before it can be quarantined")
            return [{"_id": f"{name}:orphan:{e['child_table']}:{k[e['key']['source'][0]]}",
                     "collection": name, "category": e["orphan_category"],
                     "reason": f"orphan child row: no root row for parent key {pk}",
                     "child_table": e["child_table"],
                     "raw_row": {kk: str(vv) for kk, vv in k.items()}} for k in kids]

        for pk, kids in children[e["array_path"]].items():
            if pk not in parents:
                orphans += orphan_docs(kids, pk)
        if e.get("orphan_where"):
            hidden: dict[tuple, list] = {}
            for r in select(cur, e["child_table"],
                            e["parent_key"] + e["key"]["source"] + source_columns(e),
                            substitute(e["orphan_where"], params)):
                hidden.setdefault(tuple(r[k] for k in e["parent_key"]), []).append(r)
            for pk, kids in hidden.items():
                if pk in parents:
                    sys.exit(f"{name}.{e['array_path']}: orphan_where returned rows whose "
                             f"parent {pk} does exist; the predicate does not describe "
                             "orphans and the load would quarantine live data")
                orphans += orphan_docs(kids, pk)

    # Scope is settled before the summary so the digest covers it: two batches' quarantine
    # records differ by the scope they were found in, not only by their ids.
    scope = scope_of(coll_spec, params, docs)
    for entry in quarantined + orphans:
        entry["scope"] = scope

    anomalies: dict[str, int] = {}
    for entry in quarantined + orphans:
        anomalies[entry["category"]] = anomalies.get(entry["category"], 0) + 1
    summary = {"collection": name, "documents": len(docs),
               "embedded": {e["array_path"]: sum(len(d.get(e["array_path"], []))
                                                 for d in docs)
                            for e in coll_spec.get("embeds", [])},
               "quarantined": len(quarantined) + len(orphans),
               "anomalies": anomalies, "pruned": 0,
               "digest": content_digest(docs + quarantined + orphans)}
    if "expected_documents" in coll_spec:
        summary["expected_documents"] = coll_spec["expected_documents"]
        summary["matches_census"] = len(docs) == coll_spec["expected_documents"]
    if dry_run:
        return summary, docs[:1]

    # Every gate runs on the extract before the target is touched. A scoped or truncated
    # extract must not reach the write path at all: the prune below deletes whatever this
    # load did not just read, so a short extract that got as far as writing would take the
    # valid documents with it.
    problems = anomaly_mismatches(coll_spec, anomalies)
    if summary.get("matches_census") is False:
        problems.append(f"{name}: extracted {len(docs)} rows, census says "
                        f"{coll_spec['expected_documents']}")
    if problems:
        sys.exit(f"{name}: the extract does not describe the migration the mapping declares, "
                 "so nothing is written: " + "; ".join(problems))

    # An empty source still materializes its collection: a downstream count check must see a
    # real zero rather than an absent collection it could read as "not loaded yet".
    if name not in db.list_collection_names():
        db.create_collection(name)
    install_validator(db, coll_spec, code_desc)
    if docs:
        db[name].bulk_write([ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs],
                            ordered=False)

    # Upsert alone converges on changed and added rows but not on deleted ones: a document
    # whose source row is gone would survive the rerun and the target would hold a record
    # the source does not. Within this extract's scope the unit owns everything (one
    # collection, one unit, by the write-target registration), so anything else in scope is
    # stale -- and anything outside it belongs to another batch and is left alone.
    summary["pruned"] = db[name].delete_many(
        {**scope, "_id": {"$nin": [d["_id"] for d in docs]}}
    ).deleted_count

    qcoll = (coll_spec.get("quarantine") or {}).get("collection")
    if qcoll:
        if qcoll not in db.list_collection_names():
            db.create_collection(qcoll)
        if quarantined or orphans:
            db[qcoll].bulk_write([ReplaceOne({"_id": d["_id"]}, d, upsert=True)
                                  for d in quarantined + orphans], ordered=False)
        # An anomaly that has been repaired at source must stop being reported as one,
        # otherwise the count gate would grade this unit against a healed row. Scoped the
        # same way as the documents: each record carries the scope it was found in, so a
        # later batch's load cannot erase an earlier batch's evidence.
        summary["pruned"] += db[qcoll].delete_many(
            {"collection": name,
             **{f"scope.{field}": value for field, value in scope.items()},
             "_id": {"$nin": [d["_id"] for d in quarantined + orphans]}},
        ).deleted_count
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
    ap.add_argument("--report-out", type=pathlib.Path,
                    help="write the load report here so the recon report can derive the "
                         "anomaly counts from the load instead of restating them by hand")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    params = dict(p.split("=", 1) for p in args.param)
    for k, v in params.items():
        if not PARAM_VALUE.match(v):
            sys.exit(f"--param {k}={v!r} is not a scope value; run parameters are "
                     f"interpolated into SQL and must match {PARAM_VALUE.pattern}")

    designated = designated_database()
    if args.target_db != designated:
        sys.exit(f"--target-db {args.target_db!r} is not the designated migration database "
                 f"{designated!r} recorded in {CONVENTIONS_PATH.name}; refusing to write "
                 "outside it")

    spec = json.loads(SPEC_PATH.read_text())
    colls = [c for c in spec["collections"] if c.get("unit") == args.unit]
    if not colls:
        sys.exit(f"no collections for unit '{args.unit}' in {SPEC_PATH}")

    dsn = os.environ.get(args.source_dsn_secret)
    if not dsn:
        sys.exit(f"secret '{args.source_dsn_secret}' not in environment; secrets by name only")
    user, password, conn_str = dsn.split("/", 2)

    if not args.dry_run and args.target_uri_secret not in os.environ:
        sys.exit(f"secret '{args.target_uri_secret}' not in environment; secrets by name only")
    client = None if args.dry_run else MongoClient(os.environ[args.target_uri_secret])
    db = None if args.dry_run else client[args.target_db]

    with (extract_lease(),
          oracledb.connect(user=user, password=password, dsn=conn_str) as con,
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
            report["collections"].append(summary)
            print(json.dumps(summary))
            if args.dry_run and sample:
                print(json.dumps(sample[0], indent=2, default=str))
    if not all(c["matches_census"] for c in report["collections"]):
        sys.exit("loaded document count does not match the census; not proceeding to recon")
    report["completed_at"] = dt.datetime.now(dt.UTC).isoformat()
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(report, indent=2) + "\n")
    bad = [m for c, s in zip(colls, report["collections"], strict=True)
           for m in anomaly_mismatches(c, s["anomalies"])]
    if bad:
        sys.exit("quarantine counts do not match the mapping's declared anomalies, so the "
                 "load is not the migration the contract describes: " + "; ".join(bad))


if __name__ == "__main__":
    main()
