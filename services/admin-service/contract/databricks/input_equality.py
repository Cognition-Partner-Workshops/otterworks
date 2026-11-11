"""Compare emulator input tables with the live Databricks baseline (count + order-independent hash).

Usage: TD_PG_PORT=<port> CONTRACT_KIT_PYTHON-style env + DATABRICKS_* env:
  python input_equality.py [--schema dbx_d1111_before]
Prints one JSON line per table; exits 1 on any mismatch. Credentials are read from the environment only.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import date
from decimal import Decimal

TABLES = ["gl_journal_line", "gl_account", "credit_note", "invoice_hdr", "payment", "customer_account"]
TAG = "/* run=dbx-d1111 act=consumers step=input-equality consumer=admin-service */\n"


def canon(value):
    if value is None:
        return "\\N"
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, date):
        return value.isoformat()
    return str(value).rstrip()


def digest(rows):
    total = 0
    for row in rows:
        total += int(hashlib.md5("|".join(canon(v) for v in row).encode()).hexdigest()[:15], 16)
    return {"count": len(rows), "hash": str(total)}


def emulator(table):
    import psycopg
    dsn = os.environ.get("TD_PG_DSN") or (
        f"host={os.environ.get('TD_PG_HOST', '127.0.0.1')} port={os.environ['TD_PG_PORT']} "
        f"dbname={os.environ.get('TD_PG_DB', 'teradata')} user={os.environ.get('TD_PG_USER', 'postgres')}")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='sfx_billing' "
                    "AND table_name=%s ORDER BY ordinal_position", (table,))
        cols = [r[0] for r in cur.fetchall()]
        cur.execute(f"SELECT {', '.join(cols)} FROM sfx_billing.{table}")
        return cols, cur.fetchall()


def databricks(cursor, schema, table, cols):
    cursor.execute(TAG + f"SELECT {', '.join(cols)} FROM cpw.{schema}.billing__{table}")
    rows = [tuple(r) for r in cursor.fetchall()]
    return rows, cursor.query_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", default="dbx_d1111_before", choices=["dbx_d1111_before", "dbx_d1111_after"])
    args = parser.parse_args()
    from databricks import sql
    host = os.environ["DATABRICKS_HOST"].removeprefix("https://").rstrip("/")
    ok = True
    with sql.connect(server_hostname=host, http_path="/sql/1.0/warehouses/" + os.environ["DATABRICKS_WAREHOUSE_ID"],
                     access_token=os.environ["DATABRICKS_TOKEN"], catalog="cpw", schema=args.schema) as conn:
        with conn.cursor() as cursor:
            for table in TABLES:
                cols, td_rows = emulator(table)
                dbx_rows, statement_id = databricks(cursor, args.schema, table, cols)
                td, dbx = digest(td_rows), digest(dbx_rows)
                match = td == dbx
                ok &= match
                print(json.dumps({"table": table, "schema": args.schema, "emulator": td, "databricks": dbx,
                                  "match": match, "statement_id": statement_id}))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
