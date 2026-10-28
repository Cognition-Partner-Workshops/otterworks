#!/usr/bin/env python3
"""Snapshot-extract OW_BILLING invoicing-history tables to Parquet for the Databricks load.

Reads the five OW_BILLING tables over the read-only principal, writes one Parquet file
per table under --out, then (with --upload) copies them to the UC volume
/Volumes/ow_tp/ow_tp_invoicing_history/landing/billing_history/ via `databricks fs cp`.

Column names are lowercased and Arrow types are pinned to the generated
target_schema.json so the Delta load is a bit-faithful snapshot: NUMBER(p,0) -> int64,
NUMBER(p,s) -> decimal128, DATE -> timestamp(us, tz=None), strings stay strings
(CHAR keeps its padding; the recon canonicalization rstrip_spaces applies to both sides).

  python3 extract.py --dsn-env OW_BILLING_RO_DSN --out extract/live [--upload]
  python3 extract.py --dsn-env OW_BILLING_FIXTURE_DSN --out extract/fixture [--upload]

The DSN env var holds JSON {user,password,host,port,service}. The fixture DSN for this
demo is ow_billing/ow_billing at localhost:52521/FREEPDB1 (make oracle-billing-up +
oracle-billing-seed NS=demo), supplied as the same JSON shape.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import oracledb
import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
TABLES = ["customer_master", "customer_master_hist", "entity_attr_value",
          "invoice_header", "invoice_line"]
VOLUME = "/Volumes/ow_tp/ow_tp_invoicing_history/landing/billing_history"


def arrow_field(col: dict) -> pa.Field:
    dt_ = col["delta_type"]
    name = col["name"]
    if dt_ == "BIGINT":
        typ = pa.int64()
    elif dt_.startswith("DECIMAL("):
        p, s = dt_[8:-1].split(",")
        typ = pa.decimal128(int(p), int(s))
    elif dt_ == "TIMESTAMP_NTZ":
        typ = pa.timestamp("us", tz=None)
    elif dt_ == "DOUBLE":
        typ = pa.float64()
    elif dt_ == "FLOAT":
        typ = pa.float32()
    elif dt_ == "BINARY":
        typ = pa.binary()
    else:
        typ = pa.string()
    return pa.field(name, typ)


def convert(value, col: dict):
    if value is None:
        return None
    dt_ = col["delta_type"]
    if dt_ == "BIGINT":
        return int(value)
    if dt_.startswith("DECIMAL("):
        s = int(dt_.split(",")[1].rstrip(")"))
        d = value if isinstance(value, Decimal) else Decimal(str(value))
        return d.quantize(Decimal(1).scaleb(-s)) if s >= 0 else d
    if dt_ == "STRING":
        return str(value)
    if isinstance(value, dt.datetime) or isinstance(value, dt.date):
        return value
    return value


def extract_table(conn, table: str, cols: list[dict], out_dir: Path) -> int:
    colnames = [c["name"] for c in cols]
    orac_names = [c["name"].upper() for c in cols]
    sql = f"SELECT {', '.join(orac_names)} FROM OW_BILLING.{table.upper()}"
    cur = conn.cursor()
    cur.arraysize = 5000
    cur.prefetchrows = 5000
    cur.execute(sql)
    schema = pa.schema([arrow_field(c) for c in cols])
    path = out_dir / f"{table}.parquet"
    writer = pq.ParquetWriter(path, schema)
    total = 0
    while True:
        rows = cur.fetchmany(20000)
        if not rows:
            break
        data = [[convert(v, cols[i]) for i, v in enumerate(row)] for row in rows]
        arrays = [pa.array([r[i] for r in data], type=schema.field(i).type)
                  for i in range(len(cols))]
        writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
        total += len(rows)
    writer.close()
    cur.close()
    return total


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dsn-env", default="OW_BILLING_RO_DSN")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--upload", action="store_true")
    args = p.parse_args()
    dsn = json.loads(os.environ[args.dsn_env])
    schema_map = json.loads((HERE / "target_schema.json").read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    conn = oracledb.connect(user=dsn["user"], password=dsn["password"],
                            dsn=f'{dsn["host"]}:{dsn["port"]}/{dsn["service"]}')
    for table in TABLES:
        n = extract_table(conn, table, schema_map[table], args.out)
        print(f"{table}: {n} rows -> {args.out / (table + '.parquet')}")
    conn.close()
    if args.upload:
        for table in TABLES:
            src = args.out / f"{table}.parquet"
            dst = f"{VOLUME}/{table}.parquet"
            subprocess.run(["databricks", "fs", "cp", str(src), dst, "--overwrite"], check=True)
        print(f"uploaded {len(TABLES)} files to {VOLUME}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
