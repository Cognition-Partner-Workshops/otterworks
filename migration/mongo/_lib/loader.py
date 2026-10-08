"""Spec-driven Oracle -> MongoDB loader for the UNT9 wave batches.

Reads `.migration/mapping_spec.json` (never edits it), selects each collection's
root table read-only, converts every field to its declared `bson_type` using the
field's canonicalization rules, and writes only the collections the caller names.
Planted orphan pointers are copied as-is. Secrets are read from the environment by
name only (MMP_RT_SRC_DSN, MONGODB_ATLAS_URI).
"""
from __future__ import annotations

import datetime as dt
import decimal
import json
import os
import sys
from pathlib import Path

import oracledb
import pymongo
from bson.decimal128 import Decimal128
from bson.int64 import Int64

WORKSPACE = Path(__file__).resolve().parents[3]
SPEC_PATH = WORKSPACE / ".migration" / "mapping_spec.json"
ALLOWED_PATH = WORKSPACE / ".migration" / "allowed_targets.json"
TARGET_DB = "mmp_rt_b5_oracle"
YN_TRUE = {"Y", "YES", "T", "TRUE", "1"}
YN_FALSE = {"N", "NO", "F", "FALSE", "0"}


def _oracle_connect():
    raw = os.environ["MMP_RT_SRC_DSN"]
    try:
        c = json.loads(raw)
        kw = dict(user=c["user"], password=c["password"], dsn=c["dsn"])
    except (ValueError, KeyError):
        user, rest = raw.split("/", 1)
        pwd, dsn = rest.rsplit("@", 1)
        kw = dict(user=user, password=pwd, dsn=dsn)
    oracledb.defaults.fetch_decimals = True
    return oracledb.connect(**kw)


def _rule_params(spec: dict) -> dict:
    out = {}
    for r in spec.get("canonicalization", {}).get("rules", []):
        out[r.get("name") or r["rule"]] = (r["rule"], r.get("params") or {})
    return out


def convert(value, field: dict, rule_params: dict):
    """Source value -> BSON value per declared bson_type and the field's rules."""
    if value is None:
        return None
    rules = field.get("rules") or []
    bson_type = (field.get("bson_type") or "string").lower()
    src_type = (field.get("source_type") or "").upper()
    if isinstance(value, str):
        if "rstrip_spaces" in rules or src_type.startswith("CHAR"):
            value = value.rstrip(" ")
        if value == "" and ("empty_string_is_null" in rules or bson_type != "string"):
            return None
    for name in rules:
        impl, params = rule_params.get(name, (name, {}))
        if impl == "date_string_to_date" and isinstance(value, str):
            try:
                value = dt.datetime.strptime(value.strip(), params.get("format", "%d-%b-%y"))
            except ValueError:
                # spec `unparseable`: "null" quarantines the parsed field (raw text lives in
                # the spec's `raw_field` copy); default "keep" leaves the string for recon to show
                if params.get("unparseable", "keep") == "null":
                    return None
        elif impl == "yn_to_bool" and isinstance(value, str):
            tok = value.strip().upper()
            value = True if tok in YN_TRUE else False if tok in YN_FALSE else value
        elif impl == "int_to_bool" and isinstance(value, (int, decimal.Decimal)) and not isinstance(value, bool):
            value = bool(value)
        elif impl == "csv_to_array" and isinstance(value, str):
            value = [p.strip() for p in value.split(params.get("delimiter", ",")) if p.strip() != ""]
    if bson_type in ("long", "int"):
        if isinstance(value, (int, decimal.Decimal, float)) and not isinstance(value, bool):
            return Int64(int(value)) if bson_type == "long" else int(value)
    elif bson_type in ("decimal", "decimal128"):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = decimal.Decimal(str(value))
        if isinstance(value, decimal.Decimal):
            return Decimal128(value)
    elif bson_type == "double":
        if isinstance(value, (int, decimal.Decimal)) and not isinstance(value, bool):
            return float(value)
    elif bson_type == "date":
        if isinstance(value, dt.datetime):
            return value.replace(tzinfo=None, microsecond=(value.microsecond // 1000) * 1000)
        if isinstance(value, dt.date):
            return dt.datetime(value.year, value.month, value.day)
    elif bson_type == "string":
        if isinstance(value, (int, decimal.Decimal)) and not isinstance(value, bool):
            return str(value)
    return value


def _check_targets(db_name: str, collections: list[str], spec_by_name: dict) -> None:
    allowed = json.loads(ALLOWED_PATH.read_text())["databases"]
    if db_name not in allowed:
        raise SystemExit(f"refused: {db_name} is not in .migration/allowed_targets.json")
    unknown = [c for c in collections if c not in spec_by_name]
    if unknown:
        raise SystemExit(f"refused: collections not in mapping spec: {unknown}")


def _set_path(doc: dict, path: str, value) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        doc = doc.setdefault(part, {})
    doc[parts[-1]] = value


def _attach_embed(ora, emb: dict, rows: list, cols: list[dict], docs: list[dict], rule_params: dict) -> None:
    """Embed child rows as an ordered array on their parent: parent_ref -> parent_key, ordered by the embed key then child_key."""
    pk, pref = emb["parent_key"], emb["parent_ref"]
    ref_idx = [[col["source"] for col in cols].index(src) for src in pref]
    children = {}
    ccols = list(emb["child_fields"])
    order = list(emb.get("key", {}).get("source") or []) + [k for k in emb["child_key"] if k not in (emb.get("key", {}).get("source") or [])]
    csql = "SELECT " + ", ".join(pk + [f["source"] for f in ccols]) + f" FROM {emb['child_table']} ORDER BY " + ", ".join(pk + order)
    cur = ora.cursor()
    cur.execute(csql)
    for row in cur:
        parent = tuple(row[: len(pk)])
        values = dict(zip([f["source"] for f in ccols], row[len(pk):]))
        child = {}
        for f in ccols:
            v = convert(values[f["source"]], f, rule_params)
            if v is not None:
                _set_path(child, f["target"], v)
        children.setdefault(parent, []).append(child)
    for row, doc in zip(rows, docs):
        doc[emb["array_path"]] = children.pop(tuple(row[i] for i in ref_idx), [])
    if children:
        raise SystemExit(f"refused: {sum(len(v) for v in children.values())} {emb['child_table']} rows have no parent in the loaded roots")


def _row_doc(row: tuple, cols: list[dict], key: dict, rule_params: dict) -> dict:
    doc = {}
    values = dict(zip([c["source"] for c in cols], row))
    for c in cols:
        v = convert(values[c["source"]], c, rule_params)
        if v is not None:
            _set_path(doc, c["target"], v)
    key_src, key_tgt = key["source"], key["target"]
    if isinstance(key_tgt, str):
        kv = values[key_src[0]]
        doc[key_tgt] = convert(kv, {"bson_type": "string" if isinstance(kv, str) else "long"}, rule_params)
    else:
        for s, t in zip(key_src, key_tgt):
            kv = values[s]
            doc[t] = convert(kv, {"bson_type": "string" if isinstance(kv, str) else "long"}, rule_params)
    return doc


def load(collections: list[str], db_name: str = TARGET_DB) -> dict:
    spec = json.loads(SPEC_PATH.read_text())
    spec_by_name = {c["collection"]: c for c in spec["collections"]}
    _check_targets(db_name, collections, spec_by_name)
    rule_params = _rule_params(spec)
    ora = _oracle_connect()
    mongo = pymongo.MongoClient(os.environ["MONGODB_ATLAS_URI"])
    db = mongo[db_name]
    counts = {}
    for name in collections:
        c = spec_by_name[name]
        key_cols = [{"source": s, "target": "__key__", "bson_type": None} for s in c["key"]["source"]]
        cols = list(c["fields"]) + [k for k in key_cols if k["source"] not in {f["source"] for f in c["fields"]}]
        select = [f"r.{col['source']}" for col in cols]
        joins = []
        # extended_reference: parent fields copied onto the child via an outer join (orphans keep nulls)
        for i, cf in enumerate(c.get("copied_fields") or []):
            alias = f"j{i}"
            on = " AND ".join(f"{alias}.{rm} = r.{lc}" for lc, rm in zip(cf["join"]["local"], cf["join"]["remote"]))
            joins.append(f" LEFT OUTER JOIN {cf['from_table']} {alias} ON {on}")
            for f in cf["fields"]:
                src = f"{alias}__{f['source']}"
                select.append(f"{alias}.{f['source']} AS {src}")
                cols.append({**f, "source": src})
        sql = "SELECT " + ", ".join(select) + f" FROM {c['root_table']} r" + "".join(joins)
        if c.get("root_where"):
            sql += " WHERE " + c["root_where"]
        cur = ora.cursor()
        cur.execute(sql)
        rows = list(cur)
        docs = [_row_doc(r, cols, c["key"], rule_params) for r in rows]
        for d in docs:
            d.pop("__key__", None)
        for emb in c.get("embeds") or []:
            if emb.get("shape") != "array":
                raise SystemExit(f"refused: {name} embed {emb['array_path']} shape {emb.get('shape')!r} not supported")
            _attach_embed(ora, emb, rows, cols, docs, rule_params)
        db.drop_collection(name)  # own write target only
        if docs:
            db[name].insert_many(docs, ordered=True)
        for ix in c.get("indexes") or []:
            keys = [(k, int(d)) for k, d in ix["keys"]]
            db[name].create_index(keys, unique=bool(ix.get("unique")))
        counts[name] = db[name].count_documents({})
    ora.close()
    mongo.close()
    return counts


def main(unit_file: str) -> None:
    unit = json.loads(Path(unit_file).read_text())
    counts = load(unit["collections"], unit.get("database", TARGET_DB))
    print(json.dumps({"unit_id": unit["unit_id"], "loaded": counts}))


if __name__ == "__main__":
    main(sys.argv[1])
