"""Prove (and optionally make) the Teradata emulator's inputs equal the live Databricks baseline.

  check: count + order-independent hash per table on both sides.
  seed:  replace the emulator's rows for these tables with cpw.dbx_d1111_before rows, then check.
Needs DATABRICKS_HOST/TOKEN/WAREHOUSE_ID and TD_PG_PORT (emulator); never prints secrets.
"""
import argparse, json, os
from databricks import sql
import psycopg

TABLES = ["customer_account", "subscription", "plan_catalog", "invoice_hdr", "payment"]
TAG = "/* run=dbx-d1111 act=consumers step={step} consumer=analytics-service */\n"


def pg():
    return psycopg.connect(host=os.getenv("TD_PG_HOST", "localhost"), port=int(os.environ["TD_PG_PORT"]),
                           dbname=os.getenv("TD_PG_DB", "teradata"), user=os.getenv("TD_PG_USER", "postgres"),
                           password=os.getenv("TD_PG_PASSWORD", ""))


def dbx():
    return sql.connect(server_hostname=os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/"),
                       http_path="/sql/1.0/warehouses/" + os.environ["DATABRICKS_WAREHOUSE_ID"],
                       access_token=os.environ["DATABRICKS_TOKEN"], catalog="cpw", schema="dbx_d1111_before")


def columns(pgc, table):
    rows = pgc.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='sfx_billing' "
                       "AND table_name=%s ORDER BY ordinal_position", (table,)).fetchall()
    return [(name, kind) for name, kind in rows]


def canonical(cols, dialect):
    # CHAR(n) columns compare without trailing pad (Teradata CHAR semantics); VARCHAR keeps pads.
    parts = []
    for name, kind in cols:
        text = f"CAST({name} AS STRING)" if dialect == "dbx" else f"CAST({name} AS TEXT)"
        if kind == "character":
            text = f"rtrim({text})"
        parts.append(f"coalesce({text}, '<null>')")
    return "concat_ws('|', " + ", ".join(parts) + ")"


def check(step):
    out = {}
    with pg() as pgc, dbx() as dc, dc.cursor() as cur:
        for t in TABLES:
            cols = columns(pgc, t)
            p = pgc.execute(f"SELECT count(*), coalesce(sum(('x' || substr(md5({canonical(cols, 'pg')}), 1, 15))::bit(60)::bigint), 0)::text "
                            f"FROM sfx_billing.{t}").fetchone()
            cur.execute(TAG.format(step=step) + f"SELECT count(*), CAST(coalesce(sum(CAST(conv(substr(md5({canonical(cols, 'dbx')}), 1, 15), 16, 10) AS DECIMAL(38,0))), 0) AS STRING) "
                        f"FROM cpw.dbx_d1111_before.billing__{t}")
            d = cur.fetchone()
            out[t] = {"emulator": [p[0], p[1]], "before": [d[0], d[1]], "equal": p[0] == d[0] and p[1] == d[1],
                      "statement_id": cur.query_id}
    return out


def seed():
    with pg() as pgc, dbx() as dc, dc.cursor() as cur:
        for t in TABLES:
            cols = [c for c, _ in columns(pgc, t)]
            cur.execute(TAG.format(step="seed-emulator") + f"SELECT {', '.join(cols)} FROM cpw.dbx_d1111_before.billing__{t}")
            rows = cur.fetchall()
            pgc.execute(f"DELETE FROM sfx_billing.{t}")
            with pgc.cursor().copy(f"COPY sfx_billing.{t} ({', '.join(cols)}) FROM STDIN") as copy:
                for r in rows:
                    copy.write_row(tuple(r))
        pgc.commit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["check", "seed"])
    ap.add_argument("--step", default="input-equality")
    a = ap.parse_args()
    if a.action == "seed":
        seed()
    print(json.dumps(check(a.step), indent=1))
