#!/usr/bin/env python3
"""Mapping-spec-driven loader for one migration unit: Oracle -> MongoDB Atlas.

Reads the pinned `.migration/mapping_spec.json` (never edited here), selects the
collections named on the batch ticket, and for each one:

  * drops and recreates exactly that collection (nothing else in the database),
  * loads every root row as one document typed per the spec's `bson_type`
    (NUMBER(p,0) -> Int64, NUMBER(p,s) -> Decimal128, CHAR(1) *_YN -> bool,
    DATE -> BSON date, VARCHAR2 -> string, Oracle NULL -> null),
  * embeds each `embeds[]` child table as an array under `array_path`, one element
    per child row (element key + `fields` + any extra `child_fields`, e.g. the attribute
    pattern's `attrName` next to `k`), sorted by the element key so reloads are idempotent,
  * creates every `indexes[]` entry with its `unique` flag.

Secrets are passed by environment-variable NAME; the values are never printed.
`--target-db` must be allowlisted in `.migration/allowed_targets.json` and every
collection must be in `--write-targets` (`<db>.<collection>`), or the loader refuses.
The resulting counts and collStats (no row values) are written to `--out`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import hashlib
import json
import os
import pathlib
import sys

import oracledb
from bson.decimal128 import Decimal128
from bson.int64 import Int64
from pymongo import ASCENDING, MongoClient


def _secret(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"refused: secret {name!r} is not set in the environment")
    return value


def _oracle_connect(secret_name: str):
    raw = _secret(secret_name)
    try:
        spec = json.loads(raw)
        user, password, dsn = spec["user"], spec["password"], spec["dsn"]
    except (ValueError, KeyError, TypeError):
        raise SystemExit(f"refused: {secret_name} must be canonical JSON {{user,password,dsn}}")
    conn = oracledb.connect(user=user, password=password, dsn=dsn)

    def handler(cursor, metadata):
        if metadata.type_code is oracledb.DB_TYPE_NUMBER and not (
                metadata.scale == 0 and metadata.precision):
            return cursor.var(decimal.Decimal, arraysize=cursor.arraysize)
    conn.outputtypehandler = handler
    return conn, user.upper()


def _rule_params(spec: dict) -> dict[str, dict]:
    out = {}
    for r in (spec.get("canonicalization") or {}).get("rules", []):
        out[r.get("name") or r["rule"]] = {"rule": r["rule"], "params": r.get("params") or {}}
    return out


class Converter:
    """Source value -> BSON value for one field mapping (type + load-time rules)."""

    def __init__(self, rules: dict[str, dict]):
        self.rules = rules

    def convert(self, value, field: dict):
        rule_names = field.get("rules") or []
        if isinstance(value, str):
            if any(self.rules.get(n, {}).get("rule", n) == "rstrip_spaces" for n in rule_names):
                value = value.rstrip(" ")
            if value == "":
                value = None  # d-empty-string-policy = null; Oracle never stores '' anyway
        if value is None:
            return None
        bson_type = (field.get("bson_type") or "").lower()
        for name in rule_names:
            spec = self.rules.get(name, {"rule": name, "params": {}})
            rule, params = spec["rule"], spec["params"]
            if rule == "yn_to_bool" and isinstance(value, str):
                token = value.strip().upper()
                if token in ("Y", "T", "1", "TRUE", "YES"):
                    value = True
                elif token in ("N", "F", "0", "FALSE", "NO"):
                    value = False
                else:
                    raise ValueError(f"{field['source']}: unknown Y/N token")
            elif rule == "int_to_bool" and not isinstance(value, bool):
                value = bool(int(value))
            elif rule == "csv_to_array" and isinstance(value, str):
                items = [p.strip() for p in value.split(params.get("delimiter", ","))]
                value = [p for p in items if p != ""] if params.get("drop_empty", True) else items
            elif rule == "date_string_to_date" and isinstance(value, str):
                try:
                    value = dt.datetime.strptime(value.strip(), params.get("format", "%d-%b-%y"))
                except ValueError:
                    if params.get("unparseable") == "null":
                        value = None
                    else:
                        raise
        if value is None:
            return None
        if bson_type in ("long", "int"):
            if isinstance(value, decimal.Decimal) and value != value.to_integral_value():
                raise ValueError(f"{field['source']}: non-integral value for {bson_type}")
            return Int64(int(value)) if bson_type == "long" else int(value)
        if bson_type in ("decimal", "decimal128"):
            d = value if isinstance(value, decimal.Decimal) else decimal.Decimal(str(value))
            return Decimal128(d)
        if bson_type == "double":
            return float(value)
        if bson_type == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"{field['source']}: not a bool after rules")
            return value
        if bson_type == "date":
            if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
                return dt.datetime(value.year, value.month, value.day)
            if not isinstance(value, dt.datetime):
                raise ValueError(f"{field['source']}: not a date after rules")
            if value.tzinfo is not None:
                value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
            return value
        if bson_type == "string":
            return value if isinstance(value, str) else str(value)
        if bson_type == "array":
            return list(value) if not isinstance(value, list) else value
        return value


def _key_field_mappings(coll: dict) -> list[dict]:
    """Field mapping per root key column: from decision.key_fields when present."""
    by_source = {f["source"]: f for f in (coll.get("decision") or {}).get("key_fields", [])}
    by_source.update({f["source"]: f for f in coll.get("fields", [])})
    out = []
    for col in coll["key"]["source"]:
        out.append(by_source.get(col, {"source": col, "target": col, "bson_type": "string", "rules": []}))
    return out


def _select(cur, schema: str, table: str, columns: list[str], where: str | None):
    sql = f'SELECT {", ".join(columns)} FROM {schema}.{table}'
    if where:
        sql += f" WHERE {where}"
    cur.execute(sql)
    names = [d[0] for d in cur.description]
    for row in cur:
        yield dict(zip(names, row))


def load_collection(coll: dict, conv: Converter, cur, schema: str, db, stats: dict):
    name = coll["collection"]
    key_targets = coll["key"]["target"]
    key_targets = [key_targets] if isinstance(key_targets, str) else list(key_targets)
    key_maps = _key_field_mappings(coll)
    fields = coll.get("fields", [])
    embeds = coll.get("embeds", [])

    columns = list(dict.fromkeys(coll["key"]["source"] + [f["source"] for f in fields]
                                 + [c for e in embeds for c in e.get("parent_ref", [])]))
    docs = []
    root_index: dict[tuple, dict] = {}
    for row in _select(cur, schema, coll["root_table"], columns, coll.get("root_where")):
        doc = {}
        key_vals = [conv.convert(row[m["source"]], m) for m in key_maps]
        if key_targets == ["_id"]:
            doc["_id"] = key_vals[0]
        else:
            for tgt, val in zip(key_targets, key_vals):
                doc[tgt] = val
            doc["_id"] = ":".join(str(v) for v in key_vals)  # deterministic surrogate
        for f in fields:
            doc[f["target"]] = conv.convert(row[f["source"]], f)
        for e in embeds:
            doc[e["array_path"]] = {} if e.get("shape") == "subdocument" else []
        docs.append(doc)
        for e in embeds:
            ref = tuple(row[c] for c in (e.get("parent_ref") or coll["key"]["source"]))
            root_index[(e["array_path"],) + ref] = doc

    embed_counts = {}
    for e in embeds:
        ekey = e.get("key") or {}
        ekey_targets = ekey.get("target") or []
        ekey_targets = [ekey_targets] if isinstance(ekey_targets, str) else list(ekey_targets)
        efields = e.get("fields", [])
        child_cols = list(dict.fromkeys(e["parent_key"] + list(ekey.get("source", []))
                                        + [f["source"] for f in efields]
                                        + [f["source"] for f in e.get("child_fields", [])]))
        by_source = {f["source"]: f for f in e.get("child_fields", [])}
        by_source.update({f["source"]: f for f in efields})
        n = 0
        for row in _select(cur, schema, e["child_table"], child_cols, e.get("child_where")):
            parent = root_index.get((e["array_path"],) + tuple(row[c] for c in e["parent_key"]))
            if parent is None:
                raise SystemExit(f"refused: {e['child_table']} row has no {coll['root_table']} parent")
            el = {}
            for col, tgt in zip(ekey.get("source", []), ekey_targets):
                el[tgt] = conv.convert(row[col], by_source.get(col, {"source": col, "bson_type": "string"}))
            for f in efields:
                el[f["target"]] = conv.convert(row[f["source"]], f)
            for f in e.get("child_fields", []):
                if f["target"] not in el and f["source"] in row:
                    el[f["target"]] = conv.convert(row[f["source"]], f)
            if e.get("shape") == "subdocument":
                parent[e["array_path"]] = el
            else:
                parent[e["array_path"]].append(el)
            n += 1
        if e.get("shape") != "subdocument":
            for doc in docs:
                doc[e["array_path"]].sort(key=lambda el: tuple(repr(el.get(k)) for k in ekey_targets))
        embed_counts[e["array_path"]] = n

    db.drop_collection(name)
    db.create_collection(name)
    if docs:
        db[name].insert_many(docs, ordered=True)
    created = []
    for ix in coll.get("indexes", []):
        keys = [(k, int(d)) for k, d in ix["keys"]]
        created.append(db[name].create_index(keys, unique=bool(ix.get("unique"))))
    cs = db.command("collStats", name)
    stats[name] = {
        "root_table": coll["root_table"], "source_rows": len(docs),
        "docs_inserted": db[name].count_documents({}),
        "embeds": {e["array_path"]: {"child_table": e["child_table"], "elements": embed_counts[e["array_path"]]}
                   for e in embeds},
        "indexes_created": created,
        "collStats": {k: cs.get(k) for k in ("count", "size", "storageSize", "totalIndexSize", "nindexes")},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mapping", required=True, type=pathlib.Path)
    ap.add_argument("--collections", required=True, help="comma-separated spec collections to load")
    ap.add_argument("--source-dsn-secret", required=True, help="ENV VAR NAME of the Oracle JSON DSN")
    ap.add_argument("--target-uri-secret", required=True, help="ENV VAR NAME of the Mongo URI")
    ap.add_argument("--target-db", required=True)
    ap.add_argument("--allowed-targets-file", required=True, type=pathlib.Path)
    ap.add_argument("--write-targets", required=True, help="comma-separated <db>.<collection> from the ticket")
    ap.add_argument("--schema", default=None, help="Oracle schema (default: secret user, upper-cased)")
    ap.add_argument("--out", required=True, type=pathlib.Path)
    args = ap.parse_args()

    allowed = json.loads(args.allowed_targets_file.read_text())
    if args.target_db not in allowed.get("databases", []):
        raise SystemExit(f"refused: {args.target_db} is not in {args.allowed_targets_file} databases")
    write_targets = {t.strip() for t in args.write_targets.split(",") if t.strip()}
    wanted = [c.strip() for c in args.collections.split(",") if c.strip()]
    for c in wanted:
        if f"{args.target_db}.{c}" not in write_targets:
            raise SystemExit(f"refused: {args.target_db}.{c} is not a write target of this batch")

    raw = args.mapping.read_bytes()
    spec = json.loads(raw)
    by_name = {c["collection"]: c for c in spec["collections"]}
    unknown = [c for c in wanted if c not in by_name]
    if unknown:
        raise SystemExit(f"refused: unknown collections {unknown}")

    conv = Converter(_rule_params(spec))
    conn, user = _oracle_connect(args.source_dsn_secret)
    schema = (args.schema or user).upper()
    client = MongoClient(_secret(args.target_uri_secret))
    db = client[args.target_db]
    stats: dict = {}
    try:
        with conn.cursor() as cur:
            for c in wanted:
                load_collection(by_name[c], conv, cur, schema, db, stats)
    finally:
        conn.close()
        client.close()

    manifest = {
        "kind": "unit-load", "mapping_version": spec.get("version"),
        "mapping_sha256": hashlib.sha256(raw).hexdigest(),
        "target_db": args.target_db, "schema": schema,
        "write_targets": sorted(write_targets), "loaded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "collections": stats,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    for name, s in stats.items():
        emb = ", ".join(f"{p}={v['elements']}" for p, v in s["embeds"].items())
        print(f"{name}: rows={s['source_rows']} docs={s['docs_inserted']} indexes={len(s['indexes_created'])}"
              + (f" embeds[{emb}]" if emb else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
