"""Apply the slice-0 Lakebase objects and load the reference rows from the Delta mirror.

Order: 01_schema.sql, 02_pkg_ow_util.sql, then for each table whose Postgres copy is a plain
table (not a synced table) a full reload from ow_tp.mig_unt19_20261030_slice_0 (CODES, PLANS,
TENANTS) or from the frozen snapshot (BILLING_AUDIT_LOG, 0 rows at snapshot). Rows are read
through the Databricks CLI (the sanctioned ad-hoc SQL path) with literal SELECTs and written with
literal INSERTs; the Oracle source is never touched.
"""
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import lakebase_conn as lb

HERE = Path(__file__).resolve().parent
WAREHOUSE = "565cd2fd713738c4"
MIRROR = "ow_tp.mig_unt19_20261030_slice_0"
SNAPSHOT = "ow_tp.mig_unt19_20261030_src"

LOADS = {
    "codes": (
        ["code_type", "code_val", "code_desc"],
        f"SELECT code_type, code_val, code_desc FROM {MIRROR}.codes ORDER BY code_type, code_val",
        "INSERT INTO mig_unt19_20261030_slice_0.codes (code_type, code_val, code_desc) VALUES (%s, %s, %s)"),
    "plans": (
        ["id", "code", "tier_cd", "monthly_fee", "included_units", "overage_rate", "active_yn"],
        f"SELECT id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn FROM {MIRROR}.plans ORDER BY id",
        "INSERT INTO mig_unt19_20261030_slice_0.plans (id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn) VALUES (%s, %s, %s, %s, %s, %s, %s)"),
    "tenants": (
        ["id", "name", "tax_exempt_yn", "status_cd"],
        f"SELECT id, name, tax_exempt_yn, status_cd FROM {MIRROR}.tenants ORDER BY id",
        "INSERT INTO mig_unt19_20261030_slice_0.tenants (id, name, tax_exempt_yn, status_cd) VALUES (%s, %s, %s, %s)"),
    "billing_audit_log": (
        ["log_id", "logged_at", "module", "message"],
        f"SELECT log_id, logged_at, module, message FROM {SNAPSHOT}.billing_audit_log ORDER BY log_id",
        "INSERT INTO mig_unt19_20261030_slice_0.billing_audit_log (log_id, logged_at, module, message) VALUES (%s, %s::timestamp, %s, %s)"),
}
NUMERIC_COLS = {"code_val", "tier_cd", "monthly_fee", "included_units", "overage_rate", "status_cd", "log_id"}


def delta_rows(cols: list[str], sql: str) -> list[list]:
    """The CLI returns a JSON array of {column: string} objects; values are re-typed by column."""
    r = subprocess.run(["databricks", "experimental", "aitools", "tools", "query",
                        "--warehouse", WAREHOUSE, "--output", "json", sql],
                       check=True, capture_output=True, text=True)
    data = json.loads(r.stdout)
    rows = []
    for row in data:
        rows.append([Decimal(row[c]) if c in NUMERIC_COLS and row[c] is not None else row[c]
                     for c in cols])
    return rows


def is_synced(cur, table: str) -> bool:
    cur.execute("""SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = %s AND c.relname = %s AND c.relkind IN ('v', 'f')""",
                (lb.SCHEMA, table))
    if cur.fetchone():
        return True
    cur.execute("""SELECT 1 FROM pg_description d JOIN pg_class c ON c.oid = d.objoid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                   WHERE n.nspname = %s AND c.relname = %s AND d.description ILIKE '%%synced%%'""",
                (lb.SCHEMA, table))
    return cur.fetchone() is not None


def main() -> int:
    summary = {}
    with lb.connect() as cn, cn.cursor() as cur:
        for f in ("01_schema.sql", "02_pkg_ow_util.sql"):
            cur.execute((HERE / f).read_text())
            print(f"applied {f}")
        for table, (cols, select_sql, insert_sql) in LOADS.items():
            if is_synced(cur, table):
                summary[table] = "synced table (left to the sync pipeline)"
                continue
            rows = delta_rows(cols, select_sql)
            cur.execute(f'TRUNCATE TABLE {lb.SCHEMA}."{table}"')
            if rows:
                cur.executemany(insert_sql, rows)
            if table == "billing_audit_log":
                cur.execute("SELECT coalesce(max(log_id), 0) FROM mig_unt19_20261030_slice_0.billing_audit_log")
                (mx,) = cur.fetchone()
                cur.execute(f"ALTER TABLE mig_unt19_20261030_slice_0.billing_audit_log "
                            f"ALTER COLUMN log_id RESTART WITH {int(mx) + 1}")
            cur.execute(f'SELECT COUNT(*) FROM {lb.SCHEMA}."{table}"')
            (n,) = cur.fetchone()
            summary[table] = {"delta_rows": len(rows), "lakebase_rows": n}
        cn.commit()
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
