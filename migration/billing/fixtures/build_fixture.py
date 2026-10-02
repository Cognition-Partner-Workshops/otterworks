#!/usr/bin/env python3
"""Billing fixture manifest (plan step s2.4-fixture).

Turns one deterministic run of the local Oracle Free fixture
(`make oracle-billing-up` + `make oracle-billing-seed NS=<ns>`) into the
committed "before" contract every migration unit develops against:
fixtures/<ns>.json. It joins

  * the seed's runtime manifest testdata/legacy/manifests/<ns>.json
    (git-ignored; namespace seed, batch_no, per-target rows and checksums),
  * migration/billing/census.json (live row counts and object list), and
  * read-only queries against the local fixture that enumerate the planted
    anomalies as sets (PKs, spellings, value histograms) so a recon can
    compare them with tolerances.json#planted_anomalies.compare_as == "set".

The script only ever connects to the local fixture (schema owner login on
localhost:52521/FREEPDB1, same DB_* defaults as the seed) and refuses any
other host; it never reads OW_TP_ORACLE_RO_DSN and never writes. The
session is put in SET TRANSACTION READ ONLY.

usage: python migration/billing/fixtures/build_fixture.py [--ns demo] [--check]
       --check rebuilds in memory and exits 1 if fixtures/<ns>.json differs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import oracledb

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CENSUS = REPO / "migration" / "billing" / "census.json"
TOLERANCES = REPO / "migration" / "billing" / "tolerances.json"
MANIFESTS = REPO / "testdata" / "legacy" / "manifests"
SEED_SCRIPT = "testdata/legacy/oracle_billing_seed.py"
STATIC_UPGRADE_SQL = "services/legacy-billing/db/oracle/schema/04_upgrade_static.sql"

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
SCHEMA = "OW_BILLING"
MONS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
DD_MON_YY = re.compile(r"^(\d{2})-([A-Z]{3})-(\d{2})$")
CLEAN_ACCT_CSV = re.compile(r"^\d{5}(,\d{5}){0,3}$")
BOOLEAN_SPELLINGS = {"true": ["Y", "1", "TRUE"], "false": ["N", "0"]}

# Static rows that 04_upgrade_static.sql adds on every boot (static_seed_version 2):
# the OtterWorks Admin tenant and its customer, plus everything hanging off them.
STATIC_ADMIN_TENANT_ID = "a0000000-0000-0000-0000-000000000001"
STATIC_ADMIN_CUST_ID = "40000000-0000-0000-0000-00000000a001"


def connect(args) -> oracledb.Connection:
    if args.host not in LOCAL_HOSTS:
        sys.exit(f"refusing to connect to {args.host!r}: the fixture builder only reads the local Oracle Free fixture")
    return oracledb.connect(user=args.user, password=args.password,
                            dsn=f"{args.host}:{args.port}/{args.service}")


def rows(cur, sql: str, **binds) -> list[tuple]:
    cur.execute(sql, binds)
    return cur.fetchall()


def scalar(cur, sql: str, **binds):
    cur.execute(sql, binds)
    return cur.fetchone()[0]


def sha256_set(values) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode()).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_dd_mon_yy(value: str | None) -> str:
    """Classify a legacy VARCHAR2(9) date: valid / calendar_invalid / malformed / null.

    Two-digit years follow Oracle RR: 00-49 -> 20xx, 50-99 -> 19xx.
    """
    if value is None:
        return "null"
    m = DD_MON_YY.match(value)
    if not m or m.group(2) not in MONS:
        return "malformed"
    day, mon, yy = int(m.group(1)), MONS.index(m.group(2)) + 1, int(m.group(3))
    year = 2000 + yy if yy < 50 else 1900 + yy
    try:
        dt.date(year, mon, day)
    except ValueError:
        return "calendar_invalid"
    return "valid"


def load_manifest(ns: str) -> dict:
    path = MANIFESTS / f"{ns}.json"
    if not path.exists():
        sys.exit(f"{path} not found: run `make oracle-billing-seed NS={ns}` first")
    return json.loads(path.read_text())


def seed_slice(cur, manifest: dict, ns: str) -> dict:
    """Re-derive the seed-owned rows and checksums and require them to equal the manifest."""
    batch_no = manifest["seed_legacy_params"][f"oracle.{SCHEMA}.CUSTOMER_MASTER"]["batch_no"]
    pfx = f"{ns}::"
    counts = {
        "CUSTOMER_MASTER": scalar(cur, "SELECT COUNT(*) FROM customer_master WHERE conversion_batch_no = :b", b=batch_no),
        "ENTITY_ATTR_VALUE": scalar(cur, """SELECT COUNT(*) FROM entity_attr_value WHERE entity_id IN
                                           (SELECT cust_id FROM customer_master WHERE conversion_batch_no = :b)""", b=batch_no),
        "INVOICE_HEADER": scalar(cur, "SELECT COUNT(*) FROM invoice_header WHERE batch_no = :b", b=batch_no),
        "INVOICE_LINE": scalar(cur, "SELECT COUNT(*) FROM invoice_line WHERE batch_no = :b", b=batch_no),
        "TENANTS": scalar(cur, "SELECT COUNT(*) FROM tenants WHERE SUBSTR(name, 1, LENGTH(:p)) = :p", p=pfx),
    }
    # Same recipe as oracle_billing_seed.Checksum: md5 over "pk:amount\n" in PK order (Python sort).
    checksums = {}
    for table, pk, amt, where in (
        ("CUSTOMER_MASTER", "cust_id", "cur_bal_amt", "conversion_batch_no = :b"),
        ("INVOICE_LINE", "line_id", "amount", "batch_no = :b"),
    ):
        h = hashlib.md5()
        for k, a in sorted(rows(cur, f"SELECT {pk}, {amt} FROM {table} WHERE {where}", b=batch_no)):
            h.update(f"{k}:{a:.2f}\n".encode())
        checksums[table] = h.hexdigest()

    targets = {}
    for key, tgt in manifest["targets"].items():
        table = key.rsplit(".", 1)[1]
        if counts[table] != tgt["rows"]:
            sys.exit(f"{table}: fixture has {counts[table]} seed-owned rows, manifest says {tgt['rows']}")
        if "checksum" in tgt and checksums[table] != tgt["checksum"]:
            sys.exit(f"{table}: recomputed checksum {checksums[table]} != manifest {tgt['checksum']}")
        targets[table] = {"rows": tgt["rows"], **({"checksum": tgt["checksum"],
                                                   "checksum_recipe": f"md5 of 'pk:amount\\n' over ({pk_of(table)}, {amt_of(table)}) sorted by pk"}
                                                  if "checksum" in tgt else {})}
    return {
        "namespace": ns,
        "seed": manifest["seed"],
        "seed_derivation": "int(sha256(namespace).hexdigest()[:8], 16)  (testdata/legacy/legacy_common.ns_seed)",
        "batch_no": batch_no,
        "batch_no_derivation": "seed % 90_000_000 + 1_000_000",
        "scale": manifest["seed_legacy_params"][f"oracle.{SCHEMA}.CUSTOMER_MASTER"]["scale"],
        "generator_version": manifest["generator_version"],
        "generator": SEED_SCRIPT,
        "runtime_manifest": f"testdata/legacy/manifests/{ns}.json (git-ignored; generated_at {manifest['generated_at']})",
        "ownership": {
            "CUSTOMER_MASTER": f"conversion_batch_no = {batch_no}",
            "ENTITY_ATTR_VALUE": "entity_id IN (seed-owned CUSTOMER_MASTER.cust_id)",
            "INVOICE_HEADER": f"batch_no = {batch_no}",
            "INVOICE_LINE": f"batch_no = {batch_no}",
            "TENANTS": f"name LIKE '{pfx}%'",
        },
        "targets": targets,
    }


def pk_of(table: str) -> str:
    return {"CUSTOMER_MASTER": "cust_id", "INVOICE_LINE": "line_id"}[table]


def amt_of(table: str) -> str:
    return {"CUSTOMER_MASTER": "cur_bal_amt", "INVOICE_LINE": "amount"}[table]


def table_counts(cur, census: dict) -> tuple[dict, list[str]]:
    out, diffs = {}, []
    for name, live in sorted(census["row_counts"]["tables"].items()):
        n = scalar(cur, f'SELECT COUNT(*) FROM "{name}"')
        out[name] = {"census_rows": live, "fixture_rows": n, "delta": n - live}
        if n != live:
            diffs.append(name)
    return out, diffs


def static_upgrade_rows(cur) -> dict:
    """PKs of the static_seed_version-2 rows (04_upgrade_static.sql) present in the fixture."""
    t, c = STATIC_ADMIN_TENANT_ID, STATIC_ADMIN_CUST_ID
    sets = {
        "TENANTS": [r[0] for r in rows(cur, "SELECT id FROM tenants WHERE id = :t", t=t)],
        "SUBSCRIPTIONS": [r[0] for r in rows(cur, "SELECT id FROM subscriptions WHERE tenant_id = :t ORDER BY 1", t=t)],
        "USAGE_EVENTS": [r[0] for r in rows(cur, "SELECT id FROM usage_events WHERE tenant_id = :t ORDER BY 1", t=t)],
        "INVOICES": [r[0] for r in rows(cur, "SELECT id FROM invoices WHERE tenant_id = :t ORDER BY 1", t=t)],
        "INVOICE_LINES": [r[0] for r in rows(cur, """SELECT il.id FROM invoice_lines il JOIN invoices i ON i.id = il.invoice_id
                                                      WHERE i.tenant_id = :t ORDER BY 1""", t=t)],
        "CUSTOMER_MASTER": [r[0] for r in rows(cur, "SELECT cust_id FROM customer_master WHERE cust_id = :c", c=c)],
        "ENTITY_ATTR_VALUE": [str(r[0]) for r in rows(cur, "SELECT eav_id FROM entity_attr_value WHERE entity_id = :c ORDER BY 1", c=c)],
        "FIXTURE_META": [r[0] for r in rows(cur, "SELECT marker FROM fixture_meta WHERE marker = 'static_seed_version'")],
    }
    return {k: v for k, v in sets.items() if v}


def anomaly_orphan_invoice_lines(cur, batch_no: int) -> dict:
    ids = [r[0] for r in rows(cur, """SELECT il.line_id FROM invoice_line il
                                      WHERE NOT EXISTS (SELECT 1 FROM invoice_header ih WHERE ih.invoice_id = il.invoice_id)
                                      ORDER BY il.line_id""")]
    ghost = scalar(cur, """SELECT COUNT(*) FROM invoice_line il
                           WHERE NOT EXISTS (SELECT 1 FROM invoice_header ih WHERE ih.invoice_id = il.invoice_id)
                             AND il.invoice_no LIKE '%-GHOST-%' AND il.batch_no = :b""", b=batch_no)
    return {
        "kind": "orphaned_rows",
        "target": f"oracle.{SCHEMA}.INVOICE_LINE",
        "compare_as": "set",
        "definition": "INVOICE_LINE rows whose INVOICE_ID has no INVOICE_HEADER row (no FK exists; INVOICE_NO is '<NS>-GHOST-<n>')",
        "sql": "SELECT line_id FROM invoice_line il WHERE NOT EXISTS (SELECT 1 FROM invoice_header ih WHERE ih.invoice_id = il.invoice_id)",
        "count": len(ids),
        "all_seed_owned_ghosts": ghost == len(ids),
        "set_sha256": sha256_set(ids),
        "line_ids": ids,
        "referential_checks_expected_zero": {
            "invoice_line_without_customer": scalar(cur, """SELECT COUNT(*) FROM invoice_line il
                WHERE NOT EXISTS (SELECT 1 FROM customer_master c WHERE c.cust_id = il.cust_id)"""),
            "invoice_header_without_customer": scalar(cur, """SELECT COUNT(*) FROM invoice_header ih
                WHERE NOT EXISTS (SELECT 1 FROM customer_master c WHERE c.cust_id = ih.cust_id)"""),
            "entity_attr_value_without_customer": scalar(cur, """SELECT COUNT(*) FROM entity_attr_value e
                WHERE e.entity_type = 'CUSTOMER' AND NOT EXISTS (SELECT 1 FROM customer_master c WHERE c.cust_id = e.entity_id)"""),
        },
    }


def anomaly_dirty_dates(cur) -> dict:
    bad = [(k, v) for k, v in rows(cur, "SELECT cust_id, signup_dt FROM customer_master ORDER BY cust_id")
           if parse_dd_mon_yy(v) in ("malformed", "calendar_invalid")]
    ids = [k for k, _ in bad]
    hist = Counter(v for _, v in bad)
    return {
        "kind": "dirty_dates",
        "target": f"oracle.{SCHEMA}.CUSTOMER_MASTER.SIGNUP_DT",
        "compare_as": "set",
        "definition": "SIGNUP_DT (VARCHAR2(9)) that is not a valid DD-MON-YY calendar date under Oracle RR year rule; "
                      "includes well-formed but impossible dates (31-FEB-24, 29-FEB-23)",
        "count": len(ids),
        "set_sha256": sha256_set(ids),
        "cust_ids": ids,
        "values": {v: {"count": n, "class": parse_dd_mon_yy(v)} for v, n in sorted(hist.items())},
    }


def anomaly_malformed_csv(cur) -> dict:
    bad = [(k, v) for k, v in rows(cur, "SELECT cust_id, related_acct_ids FROM customer_master ORDER BY cust_id")
           if v is not None and not CLEAN_ACCT_CSV.match(v)]
    ids = [k for k, _ in bad]
    return {
        "kind": "malformed_csv_lists",
        "target": f"oracle.{SCHEMA}.CUSTOMER_MASTER.RELATED_ACCT_IDS",
        "compare_as": "set",
        "definition": "RELATED_ACCT_IDS not matching ^\\d{5}(,\\d{5}){0,3}$ (NULL/empty is clean); "
                      "semicolons, blanks, empty items, trailing commas, non-numeric tokens",
        "count": len(ids),
        "set_sha256": sha256_set(ids),
        "cust_ids": ids,
        "values": dict(sorted(Counter(v for _, v in bad).items())),
    }


def anomaly_eav(cur, batch_no: int) -> dict:
    seed_vals = rows(cur, """SELECT attr_name, attr_value, COUNT(*) FROM entity_attr_value
                             WHERE entity_id IN (SELECT cust_id FROM customer_master WHERE conversion_batch_no = :b)
                             GROUP BY attr_name, attr_value ORDER BY 1, 2""", b=batch_no)
    by_attr: dict[str, dict[str, int]] = defaultdict(dict)
    by_value: Counter = Counter()
    for a, v, n in seed_vals:
        by_attr[a][v] = n
        by_value[v] += n
    static = rows(cur, """SELECT eav_id, attr_name, attr_value FROM entity_attr_value
                          WHERE entity_id NOT IN (SELECT cust_id FROM customer_master WHERE conversion_batch_no = :b)
                          ORDER BY 1""", b=batch_no)
    attr_types = dict(rows(cur, "SELECT attr_type, COUNT(*) FROM entity_attr_value GROUP BY attr_type ORDER BY 1"))
    return {
        "kind": "eav_boolean_spellings",
        "target": f"oracle.{SCHEMA}.ENTITY_ATTR_VALUE",
        "compare_as": "set",
        "definition": "ATTR_VALUE is free text (ATTR_TYPE always 'STR'); booleans are spelled Y/N/1/0/TRUE and mixed with "
                      "non-boolean strings per attribute. Recon compares the (attr_name, attr_value) vocabulary and counts.",
        "boolean_spellings": BOOLEAN_SPELLINGS,
        "non_boolean_values": sorted(v for v in by_value if v not in BOOLEAN_SPELLINGS["true"] + BOOLEAN_SPELLINGS["false"]),
        "attr_type_histogram": attr_types,
        "seed_slice_rows": sum(by_value.values()),
        "value_histogram": dict(sorted(by_value.items())),
        "attr_value_matrix": {a: dict(sorted(vs.items())) for a, vs in sorted(by_attr.items())},
        "static_baseline_rows": [{"eav_id": str(e), "attr_name": a, "attr_value": v} for e, a, v in static],
        "case_variant_attr_names": case_variants({a for _, a, _ in static} | set(by_attr)),
    }


def case_variants(names: set[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for n in sorted(names):
        groups[n.upper()].append(n)
    return {k: v for k, v in sorted(groups.items()) if len(v) > 1}


def yn_flags(cur, census: dict) -> dict:
    out = {}
    for t in census["tables"]:
        for c in t["columns"]:
            if c["column_name"].endswith("_YN"):
                hist = rows(cur, f'SELECT {c["column_name"]}, COUNT(*) FROM "{t["name"]}" GROUP BY {c["column_name"]} ORDER BY 1 NULLS FIRST')
                if hist:
                    out[f'{t["name"]}.{c["column_name"]}'] = {("NULL" if v is None else v): n for v, n in hist}
    return out


def string_date_columns(cur, census: dict) -> dict:
    out = {}
    for t in census["tables"]:
        for c in t["columns"]:
            if c["column_name"].endswith("_DT") and c["data_type"] == "VARCHAR2" and c["data_length"] == 9:
                hist = rows(cur, f'SELECT {c["column_name"]}, COUNT(*) FROM "{t["name"]}" GROUP BY {c["column_name"]}')
                cls: Counter = Counter()
                for v, n in hist:
                    cls[parse_dd_mon_yy(v)] += n
                out[f'{t["name"]}.{c["column_name"]}'] = {
                    "total": sum(cls.values()), "null": cls["null"], "valid": cls["valid"],
                    "calendar_invalid": cls["calendar_invalid"], "malformed": cls["malformed"],
                }
    return out


def build(args) -> dict:
    manifest = load_manifest(args.ns)
    census = json.loads(CENSUS.read_text())
    tolerances = json.loads(TOLERANCES.read_text())
    conn = connect(args)
    cur = conn.cursor()
    cur.execute("SET TRANSACTION READ ONLY")

    seed = seed_slice(cur, manifest, args.ns)
    tables, diffs = table_counts(cur, census)
    static_rows = static_upgrade_rows(cur)
    unexplained = {t: tables[t]["delta"] - len(static_rows.get(t, [])) for t in diffs
                   if tables[t]["delta"] != len(static_rows.get(t, []))}
    if unexplained:
        sys.exit(f"fixture vs census deltas not explained by {STATIC_UPGRADE_SQL}: {unexplained}")

    batch_no = seed["batch_no"]
    anomalies = [
        anomaly_orphan_invoice_lines(cur, batch_no),
        anomaly_dirty_dates(cur),
        anomaly_malformed_csv(cur),
        anomaly_eav(cur, batch_no),
    ]
    for a in anomalies:
        planted = next((p for p in manifest["planted_anomalies"] if p["kind"] == a["kind"]), None)
        if planted and planted["count"] != a["count"]:
            sys.exit(f"{a['kind']}: enumerated {a['count']} rows, seed planted {planted['count']}")
        a["in_seed_manifest"] = planted is not None

    fixture_meta = {m: v for m, v in rows(cur, "SELECT marker, value FROM fixture_meta ORDER BY 1")}
    date_columns = string_date_columns(cur, census)
    yn_columns = yn_flags(cur, census)
    conn.close()

    tenants_ns = census["row_counts"]["tenants_by_namespace"]
    return {
        "kind": "oracle-billing-fixture",
        "version": 1,
        "plan_step": "s2.4-fixture",
        "namespace": args.ns,
        "source": {
            "system": "oracle", "schema": SCHEMA, "mode": "fixture",
            "image": "container-registry.oracle.com/database/free:latest",
            "dsn": f"localhost:{args.port}/{args.service}",
            "transaction": "SET TRANSACTION READ ONLY",
            "driver": f"python-oracledb {oracledb.__version__} thin={oracledb.is_thin_mode()}",
            "fixture_meta": fixture_meta,
            "build": ["make oracle-billing-up", f"make oracle-billing-seed NS={args.ns}",
                      f"python migration/billing/fixtures/build_fixture.py --ns {args.ns}"],
            "merge_evidence": False,
            "note": "A fixture/local result is never merge evidence; a live recon report is (tolerances.json#oracle_source.mode).",
        },
        "seed": seed,
        "census": {
            "path": "migration/billing/census.json",
            "sha256": file_sha256(CENSUS),
            "captured_at": census["captured_at"],
            "objects_total": census["coverage"]["objects_total"],
            "tables_in_scope": sorted(census["row_counts"]["tables"]),
            "tenants_by_namespace": tenants_ns,
        },
        "tables": tables,
        "census_delta": {
            "tables_differing": diffs,
            "fixture_only_rows": sum(tables[t]["delta"] for t in diffs),
            "explanation": f"Every fixture-only row is a static_seed_version-2 row from {STATIC_UPGRADE_SQL} "
                           "(OtterWorks Admin tenant/customer and dependants). The live census has FIXTURE_META=1 "
                           "(no static_seed_version marker), so the live host predates that upgrade. "
                           "The seed-owned slice (seed.targets) matches the census exactly.",
            "static_upgrade_rows": static_rows,
        },
        "anomalies": anomalies,
        "legacy_representations": {
            "dd_mon_yy_string_dates": {
                "format": "DD-MON-YY stored in VARCHAR2(9); two-digit year under Oracle RR (00-49 -> 20xx, 50-99 -> 19xx)",
                "compare_as": "set of (column, class) counts; dirty rows are listed under anomalies[dirty_dates]",
                "columns": date_columns,
            },
            "yn_flags": {
                "format": "CHAR(1) Y/N, nullable (NULL reported as 'NULL')",
                "columns": yn_columns,
            },
        },
        "tolerances": {
            "path": "migration/billing/tolerances.json",
            "match_mode": tolerances["match_mode"],
            "row_diff_threshold": tolerances["row_diff_threshold"],
            "planted_anomalies": tolerances["planted_anomalies"],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ns", default="demo")
    ap.add_argument("--out", default=None, help="default: migration/billing/fixtures/<ns>.json")
    ap.add_argument("--check", action="store_true", help="rebuild and diff against the committed fixture")
    ap.add_argument("--host", default=os.environ.get("DB_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("DB_PORT", "52521")))
    ap.add_argument("--user", default=os.environ.get("DB_USER", "ow_billing"))
    ap.add_argument("--password", default=os.environ.get("DB_PASSWORD", "ow_billing"))
    ap.add_argument("--service", default=os.environ.get("DB_SERVICE", "FREEPDB1"))
    args = ap.parse_args()

    out = Path(args.out) if args.out else HERE / f"{args.ns}.json"
    fixture = build(args)
    text = json.dumps(fixture, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not out.exists() or out.read_text() != text:
            print(f"[fixture] {out} differs from a fresh build", file=sys.stderr)
            return 1
        print(f"[fixture] {out} matches a fresh build")
        return 0
    out.write_text(text)
    a = {x["kind"]: x["count"] for x in fixture["anomalies"] if "count" in x}
    print(f"[fixture] wrote {out}")
    print(f"[fixture] seed={fixture['seed']['seed']} batch_no={fixture['seed']['batch_no']} "
          f"targets={ {k: v['rows'] for k, v in fixture['seed']['targets'].items()} }")
    print(f"[fixture] anomalies={a}")
    print(f"[fixture] census delta: {fixture['census_delta']['fixture_only_rows']} fixture-only rows in "
          f"{fixture['census_delta']['tables_differing']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
