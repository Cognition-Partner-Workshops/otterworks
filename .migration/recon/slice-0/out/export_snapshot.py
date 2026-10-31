#!/usr/bin/env python3
"""Slice-0 access step (migrate skill, kind loaded_from_export).

Reads every OW_BILLING table named in .migration/slices.json through the
read-only principal inside one READ ONLY transaction, writes one CSV per
table (rows in PK order) plus the export manifest (seed-manifest contract:
row counts, md5 over ordered PK+amount, exact anomaly counts), and emits the
Delta load SQL in FK order. The source is only ever SELECTed. The source
secret is named by the committed policy.json and read from the environment.
"""
import argparse
import csv
import datetime as dt
import decimal
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import oracledb

oracledb.defaults.fetch_decimals = True
oracledb.defaults.fetch_lobs = False

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
POLICY = json.load(open(ROOT / ".migration/policy.json"))
RUN = "unt19-20261030"
CATALOG = POLICY["targets"]["catalog"]
SCHEMA = POLICY["targets"]["schema_prefix"] + "src"
VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/export"
OWNER = POLICY["source"]["schema"]
GOOD_CSV = re.compile(r"^\d{5}(,\d{5})*$")

Q_COLS = """SELECT column_name, data_type, data_precision, data_scale, char_length
            FROM all_tab_columns WHERE owner = :o AND table_name = :t ORDER BY column_id"""
Q_PK = """SELECT cc.column_name FROM all_constraints c
          JOIN all_cons_columns cc ON cc.owner = c.owner AND cc.constraint_name = c.constraint_name
          WHERE c.owner = :o AND c.table_name = :t AND c.constraint_type = 'P' ORDER BY cc.position"""
Q_FK = """SELECT c.table_name, r.table_name FROM all_constraints c
          JOIN all_constraints r ON r.owner = c.r_owner AND r.constraint_name = c.r_constraint_name
          WHERE c.owner = :o AND c.constraint_type = 'R'"""
Q_ORPHANS = """SELECT COUNT(*) FROM OW_BILLING.INVOICE_LINE l
               WHERE NOT EXISTS (SELECT 1 FROM OW_BILLING.INVOICE_HEADER h WHERE h.invoice_id = l.invoice_id)"""
NON_CRED = ("host", "port", "service", "service_name", "user", "username", "dsn")


def connect():
    creds = json.loads(os.environ[POLICY["source"]["secret"]])
    kw = {k: v for k, v in creds.items() if k not in NON_CRED}
    kw["user"] = creds.get("user") or creds["username"]
    if "dsn" in creds:
        kw["dsn"] = creds["dsn"]
    else:
        kw["dsn"] = f"{creds['host']}:{creds['port']}/{creds.get('service') or creds['service_name']}"
    return oracledb.connect(**kw)


def target_type(data_type, p, s):
    t = data_type.upper()
    if t == "NUMBER":
        if p is None and s is None:
            return "decimal(38,10)"
        if p is None:
            return "decimal(38,0)" if s == 0 else f"decimal(38,{s})"
        if s in (None, 0):
            return "bigint" if p <= 18 else f"decimal({p},0)"
        return f"decimal({p},{s})"
    if t == "FLOAT":
        return "decimal(38,10)"
    if t == "BINARY_FLOAT":
        return "float"
    if t == "BINARY_DOUBLE":
        return "double"
    if t in ("VARCHAR2", "NVARCHAR2", "CHAR", "NCHAR", "CLOB", "NCLOB", "LONG"):
        return "string"
    if t == "DATE" or re.fullmatch(r"TIMESTAMP\(\d+\)", t):
        return "timestamp_ntz"
    if t.startswith("TIMESTAMP"):
        return "timestamp"
    if t == "RAW":
        return "binary"
    return None


def cast_expr(col, ttype):
    if ttype is None or ttype == "string":
        return f"`{col}`"
    if ttype == "binary":
        return f"unhex(`{col}`) AS `{col}`"
    return f"CAST(`{col}` AS {ttype.upper()}) AS `{col}`"


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, decimal.Decimal):
        return format(v, "f")
    if isinstance(v, dt.datetime):
        return v.isoformat(sep=" ")
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        return v.hex()
    return str(v)


def fk_order(tables, fks):
    deps = {t: set() for t in tables}
    for child, parent in fks:
        if child in deps and parent in deps and child != parent:
            deps[child].add(parent)
    order, placed = [], set()
    while len(order) < len(tables):
        ready = sorted(t for t in tables if t not in placed and deps[t] <= placed)
        if not ready:
            raise SystemExit(f"FK cycle among {sorted(set(tables) - placed)}")
        order.extend(ready)
        placed.update(ready)
    return order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="local directory for the CSV export (not committed)")
    args = ap.parse_args()
    export_dir = Path(args.out)
    export_dir.mkdir(parents=True, exist_ok=True)
    load_dir = OUT / "load"
    load_dir.mkdir(exist_ok=True)
    for old in load_dir.glob("*.sql"):
        old.unlink()

    slices = json.load(open(ROOT / ".migration/slices.json"))
    tables = sorted({t.split(".", 1)[1] for s in slices["slices"] for t in s["tables"]})
    owner_of = {t.split(".", 1)[1]: s["id"] for s in slices["slices"] for t in s["tables"]}

    conn = connect()
    cur = conn.cursor()
    cur.execute("SET TRANSACTION READ ONLY")
    snapshot_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    cur.execute(Q_FK, o=OWNER)
    order = fk_order(tables, [(c, p) for c, p in cur.fetchall()])

    manifest_targets, type_gaps, anomalies = {}, [], []
    for i, t in enumerate(order, 1):
        cur.execute(Q_COLS, o=OWNER, t=t)
        cols = cur.fetchall()
        cur.execute(Q_PK, o=OWNER, t=t)
        pk = [r[0] for r in cur.fetchall()]
        if not pk:
            raise SystemExit(f"{t}: no primary key; ordered export needs one")
        col_names = [c[0] for c in cols]
        idx = {c: j for j, c in enumerate(col_names)}
        cur.execute(f'SELECT {", ".join(col_names)} FROM {OWNER}.{t} ORDER BY {", ".join(pk)}')
        n = 0
        path = export_dir / f"{t}.csv"
        pairs = []
        dirty = bad_csv = 0
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow([c.lower() for c in col_names])
            while True:
                rows = cur.fetchmany(5000)
                if not rows:
                    break
                for r in rows:
                    w.writerow([fmt(v) for v in r])
                    n += 1
                    if t == "CUSTOMER_MASTER":
                        pairs.append((r[idx["CUST_ID"]], f"{r[idx['CUR_BAL_AMT']]:.2f}"))
                        try:
                            dt.datetime.strptime(str(r[idx["SIGNUP_DT"]]), "%d-%b-%y")
                        except (ValueError, TypeError):
                            dirty += 1
                        rel = r[idx["RELATED_ACCT_IDS"]]
                        if rel is not None and not GOOD_CSV.match(str(rel)):
                            bad_csv += 1
                    elif t == "INVOICE_LINE":
                        pairs.append((r[idx["LINE_ID"]], f"{r[idx['AMOUNT']]:.2f}"))
        entry = {"rows": n, "pk": pk, "slice": owner_of[t], "file": f"{VOLUME}/{t}.csv",
                 "bytes": path.stat().st_size, "delta": f"{CATALOG}.{SCHEMA}.{t.lower()}"}
        if pairs:
            h = hashlib.md5()
            for pk_v, amt in sorted(pairs):
                h.update(f"{pk_v}:{amt}\n".encode())
            entry["checksum"] = h.hexdigest()
            entry["checksum_rule"] = "md5 of 'pk:amount\\n' lines in PK order (testdata/legacy/oracle_billing_seed.py Checksum)"
        manifest_targets[f"oracle.{OWNER}.{t}"] = entry
        if t == "CUSTOMER_MASTER":
            anomalies += [
                {"kind": "dirty_dates", "target": f"oracle.{OWNER}.CUSTOMER_MASTER.SIGNUP_DT", "count": dirty,
                 "rule": "SIGNUP_DT does not parse as DD-MON-YY"},
                {"kind": "malformed_csv_lists", "target": f"oracle.{OWNER}.CUSTOMER_MASTER.RELATED_ACCT_IDS",
                 "count": bad_csv, "rule": "non-null value not matching ^\\d{5}(,\\d{5})*$"},
            ]

        schema_parts, select_parts = [], []
        for name, data_type, p, s, _clen in cols:
            ttype = target_type(data_type, p, s)
            if ttype is None:
                type_gaps.append({"table": t, "column": name, "source_type": data_type})
            schema_parts.append(f"`{name.lower()}` string")
            select_parts.append(cast_expr(name.lower(), ttype))
        schema = ", ".join(schema_parts)
        stmt = (
            f"CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.{t.lower()}\n"
            f"COMMENT 'frozen snapshot of {OWNER}.{t} exported {snapshot_at} (run {RUN}, slice-0 access)'\n"
            f"AS SELECT\n  " + ",\n  ".join(select_parts) + "\n"
            f"FROM read_files('{VOLUME}/{t}.csv', format => 'csv', header => true, multiLine => true,\n"
            f"  escape => '\"', nullValue => '', inferSchema => false, mode => 'FAILFAST',\n"
            f"  schema => '{schema}');\n"
        )
        (load_dir / f"{i:02d}_{t.lower()}.sql").write_text(stmt)
        print(f"[export] {i:02d} {t}: {n} rows -> {path.name}", flush=True)

    cur.execute(Q_ORPHANS)
    anomalies.insert(0, {"kind": "orphaned_rows", "target": f"oracle.{OWNER}.INVOICE_LINE",
                         "count": int(cur.fetchone()[0]),
                         "rule": "INVOICE_LINE.invoice_id with no INVOICE_HEADER row"})
    conn.rollback()
    conn.close()

    manifest = {
        "run": RUN, "slice": "slice-0", "kind": "loaded_from_export", "mode": "snapshot",
        "generator_version": "1",
        "source": {"family": POLICY["source"]["family"], "schema": OWNER,
                   "principal_secret": POLICY["source"]["secret"],
                   "isolation": "SET TRANSACTION READ ONLY (one consistent read point for every table)"},
        "snapshot_at": snapshot_at,
        "volume": VOLUME,
        "fk_order": order,
        "targets": manifest_targets,
        "planted_anomalies": anomalies,
        "type_gaps": type_gaps,
    }
    (OUT / "export_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[export] manifest: {OUT / 'export_manifest.json'}; load SQL in {load_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
