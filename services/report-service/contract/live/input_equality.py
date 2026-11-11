"""Prove the Teradata emulator inputs equal cpw.dbx_d1111_before (count + order-independent hash).

Env: DATABRICKS_HOST/TOKEN/WAREHOUSE_ID, TD_PG_PORT (emulator). Optional RECORD=true inserts one
row per table into cpw.dbx_d1111_parity.consumer_contracts. Exit 1 on any mismatch.
"""
import os
import sys

import psycopg
from databricks import sql

TABLES = ["customer_account", "gl_account", "gl_journal_line", "invoice_hdr", "payment"]
STEP = os.environ.get("STEP", "input-equality")
TAG = f"/* run=dbx-d1111 act=consumers step={STEP} consumer=report-service */\n"


def canon(columns, char_cols, dialect):
    parts = []
    for name, kind in columns:
        col = name if dialect == "dbx" else f'"{name.lower()}"'
        expr = f"rtrim(CAST({col} AS STRING))" if dialect == "dbx" else f"rtrim(CAST({col} AS TEXT))"
        if name.lower() not in char_cols:
            expr = f"CAST({col} AS STRING)" if dialect == "dbx" else f"CAST({col} AS TEXT)"
        parts.append(f"coalesce({expr}, '~')")
    return "concat_ws('|', " + ", ".join(parts) + ")"


def main():
    host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
    dbx = sql.connect(server_hostname=host, http_path="/sql/1.0/warehouses/" + os.environ["DATABRICKS_WAREHOUSE_ID"],
                      access_token=os.environ["DATABRICKS_TOKEN"], catalog="cpw", schema="dbx_d1111_after")
    pg = psycopg.connect(host="127.0.0.1", port=int(os.environ["TD_PG_PORT"]), dbname="teradata", user="postgres")
    failed = False
    results = []
    for table in TABLES:
        cur = dbx.cursor()
        cur.execute(TAG + f"DESCRIBE TABLE cpw.dbx_d1111_before.billing__{table}")
        columns = [(r[0], r[1]) for r in cur.fetchall() if r[0] and not r[0].startswith("#")]
        with pg.cursor() as pc:
            pc.execute("SELECT column_name, data_type FROM information_schema.columns "
                       "WHERE table_schema='sfx_billing' AND table_name=%s", (table,))
            pg_types = dict(pc.fetchall())
            char_cols = {c for c, t in pg_types.items() if t == "character"}
            columns = [c for c in columns if c[0].lower() in pg_types]
            pc.execute(f"SELECT count(*), coalesce(sum(('x' || substr(md5({canon(columns, char_cols, 'pg')}), 1, 15))"
                       f"::bit(60)::bigint), 0) FROM sfx_billing.{table}")
            pg_count, pg_hash = pc.fetchone()
        cur.execute(TAG + f"SELECT count(*), coalesce(sum(CAST(conv(substr(md5({canon(columns, char_cols, 'dbx')}), 1, 15), 16, 10) AS DECIMAL(20, 0))"
                    f" ), 0) FROM cpw.dbx_d1111_before.billing__{table}")
        dbx_count, dbx_hash = cur.fetchone()
        statement_id = cur.query_id
        ok = int(pg_count) == int(dbx_count) and int(pg_hash) == int(dbx_hash)
        failed |= not ok
        detail = (f"emulator count={pg_count} hash={pg_hash}; before count={dbx_count} hash={int(dbx_hash)}; "
                  f"cols={len(columns)}")
        results.append((table, ok, detail, statement_id))
        print(f"{table}: {'MATCH' if ok else 'MISMATCH'} {detail} statement_id={statement_id}")
    if os.environ.get("RECORD") == "true":
        cur = dbx.cursor()
        for table, ok, detail, statement_id in results:
            cur.execute(TAG + "INSERT INTO cpw.dbx_d1111_parity.consumer_contracts "
                        "(consumer, check_name, path, outcome, detail, statement_id, recorded_at) "
                        "VALUES ('report-service', ?, 'oldpath-input', ?, ?, ?, current_timestamp())",
                        [f"{STEP}:{table}", "pass" if ok else "fail", detail, statement_id])
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
