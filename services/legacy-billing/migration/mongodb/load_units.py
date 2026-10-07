#!/usr/bin/env python3
"""Spec-driven loader: OW_BILLING (Oracle) -> MongoDB, one mapping-spec collection per unit.

Reads `.migration/mapping_spec.json` and writes exactly the documents the recon harness
grades: `key.target` (`_id` or composite fields), every `fields[]` entry converted by its
`bson_type` + canonicalization `rules`, and every `embeds[]` array keyed by the embed's
`key`. Loader-side obligations the spec cannot express (units.json `loader_obligations`)
are the per-unit hooks in DERIVED.

Secrets are passed by NAME (env var); the value is never printed. Writes go only to
`--target-db` (must be in `.migration/allowed_targets.json`) and only to the collections in
`--write-targets`; anything else is refused before a connection is opened. A reload empties
the unit's own collection with delete_many({}) — nothing is ever dropped.

Usage (from $HOME, absolute paths):
  .venvs/recon/bin/python <repo>/services/legacy-billing/migration/mongodb/load_units.py \
    --spec <repo>/.migration/mapping_spec.json --allowed-targets <repo>/.migration/allowed_targets.json \
    --units codes,tenants --write-targets mmp_rt_b3_oracle.codes,mmp_rt_b3_oracle.tenants \
    --source-dsn-secret MMP_RT_SRC_DSN --target-uri-secret MONGODB_ATLAS_URI \
    --target-db mmp_rt_b3_oracle --schema OW_BILLING --report /tmp/load.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import json
import os
import re
import sys
import time
from typing import Any

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*$")
YN_TRUE = {"Y", "T", "1", "TRUE", "YES"}
YN_FALSE = {"N", "F", "0", "FALSE", "NO"}
BATCH = 500


def ident(name: str) -> str:
    if not IDENT.match(name):
        raise SystemExit(f"refused: not a plain identifier: {name!r}")
    return name


def secret(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"refused: secret {name} is not set in the environment")
    return value


class Converter:
    """bson_type + rules -> BSON value. Mirrors the harness canonicalization so the loaded
    value is what the rules converge to (dates parsed, CSV split, Y/N -> bool, NUMBER ->
    Int64/Decimal128). NULL becomes a missing field when the field carries
    `null_missing_equiv`, an explicit null otherwise."""

    def __init__(self, spec: dict):
        self.rule_params: dict[str, dict] = {}
        self.rule_base: dict[str, str] = {}
        for r in spec.get("canonicalization", {}).get("rules", []):
            name = r.get("name") or r.get("rule")
            self.rule_params[name] = r.get("params") or {}
            self.rule_base[name] = r.get("rule")

    def base(self, rule: str) -> str:
        return self.rule_base.get(rule) or rule.split(":", 1)[0]

    def params(self, rule: str) -> dict:
        return self.rule_params.get(rule, {})

    def convert(self, value: Any, field: dict) -> tuple[Any, dict]:
        """Return (bson_value, extras). extras are sibling fields to write (e.g. *Raw)."""
        from bson.decimal128 import Decimal128
        from bson.int64 import Int64

        rules = field.get("rules") or []
        bases = [self.base(r) for r in rules]
        bt = (field.get("bson_type") or "").lower()
        extras: dict[str, Any] = {}
        if isinstance(value, str) and "rstrip_spaces" in bases:
            value = value.rstrip(" ")
        if value is None or (isinstance(value, str) and value == ""):
            return None, extras
        if bt in ("long", "int"):
            return Int64(int(value)), extras
        if bt in ("decimal", "decimal128"):
            return Decimal128(value if isinstance(value, decimal.Decimal) else decimal.Decimal(str(value))), extras
        if bt == "double":
            return float(value), extras
        if bt == "bool":
            if isinstance(value, bool):
                return value, extras
            token = str(value).strip().upper()
            if token in YN_TRUE:
                return True, extras
            if token in YN_FALSE:
                return False, extras
            return value, extras  # unknown token stays as-is so recon surfaces it
        if bt == "array":
            if isinstance(value, str):
                rule = next((r for r, b in zip(rules, bases) if b == "csv_to_array"), None)
                p = self.params(rule) if rule else {}
                items = [x.strip() for x in value.split(p.get("delimiter", ","))]
                if p.get("drop_empty", True):
                    items = [x for x in items if x != ""]
                return items, extras
            return list(value), extras
        if bt == "date":
            if isinstance(value, dt.datetime):
                return value.replace(microsecond=(value.microsecond // 1000) * 1000), extras
            if isinstance(value, dt.date):
                return dt.datetime(value.year, value.month, value.day), extras
            if isinstance(value, str):
                # text date (F49): keep the verbatim string next to the parsed value;
                # an unparseable value yields no parsed field at all.
                extras[field["target"] + "Raw"] = value
                rule = next((r for r, b in zip(rules, bases) if b == "date_string_to_date"), None)
                fmt = field.get("date_format") or (self.params(rule).get("format") if rule else None) or "%d-%b-%y"
                try:
                    return dt.datetime.strptime(value.strip(), fmt), extras
                except ValueError:
                    return None, extras
            return value, extras
        if isinstance(value, decimal.Decimal):
            return Int64(int(value)) if value == value.to_integral_value() else Decimal128(value), extras
        return value, extras


def put(doc: dict, field: dict, value: Any, conv: Converter) -> None:
    bson_value, extras = conv.convert(value, field)
    doc.update(extras)
    if bson_value is None:
        if "null_missing_equiv" not in [conv.base(r) for r in field.get("rules") or []]:
            doc[field["target"]] = None
        return
    doc[field["target"]] = bson_value


# ---- loader-side obligations the mapping spec cannot express (units.json loader_obligations)

def derive_customer_master(unit: str, docs: list[dict], rows: dict[str, dict], cur) -> dict:
    """F48: tenantResolved = TENANT_ID IN (SELECT ID FROM TENANTS); tenantId stays raw."""
    cur.execute("SELECT id FROM tenants")
    tenant_ids = {r[0] for r in cur.fetchall()}
    resolved = 0
    for d in docs:
        ok = rows[d["_id"]].get("TENANT_ID") in tenant_ids
        d["tenantResolved"] = ok
        resolved += int(ok)
    return {"tenantResolved_true": resolved, "tenantResolved_false": len(docs) - resolved,
            "signupDt_missing": sum(1 for d in docs if "signupDt" not in d),
            "signupDtRaw_present": sum(1 for d in docs if "signupDtRaw" in d)}


DERIVED = {"customerMaster": derive_customer_master}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--allowed-targets", required=True)
    ap.add_argument("--units", required=True, help="comma-separated mapping-spec collection names")
    ap.add_argument("--write-targets", required=True, help="comma-separated db.collection the ticket allows")
    ap.add_argument("--source-dsn-secret", required=True)
    ap.add_argument("--target-uri-secret", required=True)
    ap.add_argument("--target-db", required=True)
    ap.add_argument("--schema", default="OW_BILLING")
    ap.add_argument("--report", help="write a JSON load report here")
    ap.add_argument("--dry-run", action="store_true", help="read and convert, write nothing")
    args = ap.parse_args()

    spec = json.load(open(args.spec))
    allowed = json.load(open(args.allowed_targets)).get("databases", [])
    if args.target_db not in allowed:
        raise SystemExit(f"refused: --target-db {args.target_db!r} is not in {args.allowed_targets}")
    units = [u for u in args.units.split(",") if u]
    targets = {t for t in args.write_targets.split(",") if t}
    for t in targets:
        if t.split(".", 1)[0] != args.target_db:
            raise SystemExit(f"refused: write target {t} is outside --target-db {args.target_db}")
    by_name = {c["collection"]: c for c in spec["collections"]}
    for u in units:
        if u not in by_name:
            raise SystemExit(f"refused: {u!r} is not a collection of {args.spec} ({spec.get('version')})")
        if f"{args.target_db}.{u}" not in targets:
            raise SystemExit(f"refused: {args.target_db}.{u} is not in --write-targets (plan gap, halt)")

    import oracledb
    from bson.int64 import Int64
    from pymongo import ASCENDING, DESCENDING, MongoClient

    oracledb.defaults.fetch_decimals = True
    s = json.loads(secret(args.source_dsn_secret))
    conn = oracledb.connect(user=s["user"], password=s["password"], dsn=s["dsn"])
    cur = conn.cursor()
    cur.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {ident(args.schema)}")
    conv = Converter(spec)
    client = None if args.dry_run else MongoClient(secret(args.target_uri_secret))
    db = None if client is None else client[args.target_db]

    report: dict[str, Any] = {"kind": "load-report", "spec_version": spec.get("version"),
                              "target_db": args.target_db, "dry_run": args.dry_run,
                              "started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "units": {}}
    source_queries = 0
    for u in units:
        t0 = time.time()
        c = by_name[u]
        key_src = [ident(k) for k in c["key"]["source"]]
        key_tgt = c["key"]["target"]
        key_tgt = [key_tgt] if isinstance(key_tgt, str) else list(key_tgt)
        key_fields = {k["source"]: k for k in c.get("decision", {}).get("key_fields", [])}
        fields = c.get("fields", [])
        embeds = [e for e in c.get("embeds", []) if e.get("parent_key") and e.get("key")]
        cols = list(dict.fromkeys(key_src + [ident(f["source"]) for f in fields]
                                  + [ident(x) for e in embeds for x in e.get("parent_ref") or key_src]))
        cur.execute(f"SELECT {', '.join(cols)} FROM {ident(c['root_table'])}")
        source_queries += 1
        rows: dict[Any, dict] = {}
        docs: list[dict] = []
        for rec in cur:
            row = dict(zip(cols, rec))
            doc: dict[str, Any] = {}
            kvals = []
            for ks, kt in zip(key_src, key_tgt):
                kf = key_fields.get(ks, {"bson_type": "", "rules": []})
                kv, _ = conv.convert(row[ks], kf)
                if kv is None:
                    raise SystemExit(f"refused: NULL key {ks} on {c['root_table']}")
                doc[kt] = kv
                kvals.append(kv)
            for f in fields:
                put(doc, f, row[f["source"]], conv)
            rkey = kvals[0] if len(kvals) == 1 else tuple(kvals)
            rows[rkey] = row
            docs.append(doc)
        embed_stats = {}
        for e in embeds:
            pk = [ident(x) for x in e["parent_key"]]
            pref = [ident(x) for x in (e.get("parent_ref") or key_src)]
            ek_src = [ident(x) for x in e["key"]["source"]]
            ek_tgt = e["key"]["target"]
            ek_tgt = [ek_tgt] if isinstance(ek_tgt, str) else list(ek_tgt)
            efields = e.get("fields", [])
            ekf = {k["source"]: k for k in e.get("child_fields", []) if k["source"] in ek_src}
            ecols = list(dict.fromkeys(pk + ek_src + [ident(f["source"]) for f in efields]))
            cur.execute(f"SELECT {', '.join(ecols)} FROM {ident(e['child_table'])}")
            source_queries += 1
            parent_index = {}
            for rkey, row in rows.items():
                pv = tuple(row[x] for x in pref)
                parent_index[pv[0] if len(pv) == 1 else pv] = rkey
            doc_by_key = {}
            for d, rkey in zip(docs, rows.keys()):
                doc_by_key[rkey] = d
            attached = orphans = 0
            for rec in cur:
                erow = dict(zip(ecols, rec))
                pv = tuple(erow[x] for x in pk)
                rkey = parent_index.get(pv[0] if len(pv) == 1 else pv)
                if rkey is None:
                    orphans += 1
                    continue
                el: dict[str, Any] = {}
                for ks, kt in zip(ek_src, ek_tgt):
                    el[kt], _ = conv.convert(erow[ks], ekf.get(ks, {"bson_type": "", "rules": []}))
                for f in efields:
                    put(el, f, erow[f["source"]], conv)
                doc_by_key[rkey].setdefault(e["array_path"], []).append(el)
                attached += 1
            embed_stats[e["array_path"]] = {"child_table": e["child_table"], "elements": attached,
                                            "orphan_child_rows": orphans}
        derived = DERIVED[u](u, docs, rows, cur) if u in DERIVED else {}
        if u in DERIVED:
            source_queries += 1
        written = 0
        index_names: list[str] = []
        if not args.dry_run:
            coll = db[u]
            coll.delete_many({})
            for i in range(0, len(docs), BATCH):
                if docs[i:i + BATCH]:
                    written += len(coll.insert_many(docs[i:i + BATCH], ordered=True).inserted_ids)
            for ix in c.get("indexes", []):
                keys = [(k, ASCENDING if d == 1 else DESCENDING) for k, d in ix["keys"]]
                index_names.append(coll.create_index(keys, unique=bool(ix.get("unique"))))
        report["units"][u] = {"root_table": c["root_table"], "source_rows": len(docs),
                              "documents_written": written, "embeds": embed_stats,
                              "derived": derived, "indexes": index_names,
                              "elapsed_s": round(time.time() - t0, 3)}
        print(f"{u}: {len(docs)} rows -> {written} docs; embeds {embed_stats or '-'}; derived {derived or '-'}; indexes {index_names}")
    report["source_queries"] = source_queries
    report["source_concurrency"] = 1
    report["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    if args.report:
        with open(args.report, "w") as fh:
            json.dump(report, fh, indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
