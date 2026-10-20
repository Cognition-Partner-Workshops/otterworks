"""Shared pieces for the Commission Pay Oracle -> PostgreSQL 16 move.

Connections, the table inventory, value canonicalisation and the control
metrics computed identically on both engines. Every money and percentage
value stays a Decimal end to end; nothing is compared through float.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal

import oracledb
import psycopg

oracledb.defaults.fetch_decimals = True

ORA_SCHEMAS = ("COMMISSION_PAY", "COMMISSION_DW")

# (schema, table, primary-key columns, control-sum columns), in load order.
TABLES = [
    ("commission_pay", "products", ("product_code",), ()),
    ("commission_pay", "agents", ("agent_id",), ()),
    ("commission_pay", "policies", ("policy_id",), ("annual_premium",)),
    ("commission_pay", "commission_rates", ("rate_id",), ("rate_pct",)),
    ("commission_pay", "commission_splits", ("split_id",), ("split_pct",)),
    ("commission_pay", "commission_ledger", ("ledger_id",), ("split_pct", "base_premium", "commission_amt")),
    ("commission_pay", "rate_audit_log", ("audit_id",), ()),
    ("commission_pay", "fixture_meta", ("initialized_at",), ()),
    ("commission_dw", "dim_agent", ("agent_key",), ()),
    ("commission_dw", "dim_product", ("product_key",), ()),
    ("commission_dw", "dim_period", ("period_key",), ()),
    ("commission_dw", "fact_commission", ("fact_id",), ("split_pct", "base_premium", "commission_amt")),
]
MV = ("commission_dw", "mv_agent_commission_summary",
      ("agent_code", "period_month", "line_of_business"), ("policy_rows", "total_commission"))
RELATIONS = TABLES + [MV]

LEDGER = "commission_pay.commission_ledger"
AGENTS = "commission_pay.agents"
RATES = "commission_pay.commission_rates"
# The legacy formula from COMMISSION_PKG.calculate_policy_commission.
UNROUNDED = "l.base_premium / 12 * r.rate_pct / 100 * l.split_pct / 100"


def oracle_connect(user: str = "commission_dw") -> oracledb.Connection:
    """COMMISSION_DW by default: it owns the warehouse and can read the OLTP schema."""
    port = os.environ.get("INSURANCE_DB_PORT", "51521")
    return oracledb.connect(user=user, password=user, dsn=f"127.0.0.1:{port}/FREEPDB1")


def pg_connect(user: str = "commission_dw") -> psycopg.Connection:
    port = os.environ.get("INSURANCE_PG_PORT", "52432")
    password = os.environ.get("INSURANCE_PG_PWD", "Workshop123") if user == "postgres" else user
    return psycopg.connect(host="127.0.0.1", port=port, dbname="commission",
                           user=user, password=password)


def query(conn, sql: str, params=None) -> list[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(sql, params or ())
        return list(cur.fetchall())
    finally:
        cur.close()


def canon(value):
    """One textual form per value, so Oracle and PostgreSQL rows compare exactly."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("unexpected boolean")
    if isinstance(value, float):
        raise TypeError(f"float leaked into the comparison: {value!r}")
    if isinstance(value, (int, Decimal)):
        d = Decimal(value)
        return "0" if d == 0 else format(d.normalize(), "f")
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def oracle_columns(conn, schema: str, table: str) -> list[str]:
    rows = query(conn, """
        SELECT LOWER(column_name) FROM all_tab_columns
         WHERE owner = :1 AND table_name = :2 ORDER BY column_id""",
                 [schema.upper(), table.upper()])
    return [r[0] for r in rows]


def fetch_rows(conn, schema: str, table: str, columns: list[str], pk) -> dict:
    cols = ", ".join(columns)
    order = ", ".join(pk)
    rows = query(conn, f"SELECT {cols} FROM {schema}.{table} ORDER BY {order}")
    pk_idx = [columns.index(c) for c in pk]
    out = {}
    for row in rows:
        canon_row = tuple(canon(v) for v in row)
        key = "|".join(str(canon_row[i]) for i in pk_idx)
        if key in out:
            raise ValueError(f"duplicate key {key} in {schema}.{table}")
        out[key] = canon_row
    return out


def _dec(value) -> str:
    return canon(Decimal(value))


def control_metrics(conn) -> dict:
    """Deterministic control figures; the same SQL runs on both engines."""
    m: dict = {"tables": {}}
    for schema, table, _pk, sums in RELATIONS:
        exprs = ["COUNT(*)"] + [f"COALESCE(SUM({c}), 0)" for c in sums]
        row = query(conn, f"SELECT {', '.join(exprs)} FROM {schema}.{table}")[0]
        m["tables"][f"{schema}.{table}"] = {
            "rows": int(row[0]),
            "sums": {c: _dec(v) for c, v in zip(sums, row[1:])},
        }

    def grouped(sql):
        return {str(k): {"rows": int(n), "commission_amt": _dec(s)} for k, n, s in query(conn, sql)}

    m["ledger_by_agent"] = grouped(f"""
        SELECT a.agent_code, COUNT(*), SUM(l.commission_amt)
          FROM {LEDGER} l JOIN {AGENTS} a ON a.agent_id = l.agent_id
         GROUP BY a.agent_code ORDER BY a.agent_code""")
    m["ledger_by_period"] = grouped(f"""
        SELECT l.period_month, COUNT(*), SUM(l.commission_amt)
          FROM {LEDGER} l GROUP BY l.period_month ORDER BY l.period_month""")
    m["ledger_by_agent_period"] = grouped(f"""
        SELECT a.agent_code || ' ' || l.period_month, COUNT(*), SUM(l.commission_amt)
          FROM {LEDGER} l JOIN {AGENTS} a ON a.agent_id = l.agent_id
         GROUP BY a.agent_code || ' ' || l.period_month
         ORDER BY a.agent_code || ' ' || l.period_month""")
    m["mv_rows"] = {
        f"{code} {period} {lob}": {"full_name": name, "policy_rows": int(n), "total_commission": _dec(t)}
        for code, name, period, lob, n, t in query(conn, f"""
            SELECT agent_code, full_name, period_month, line_of_business, policy_rows, total_commission
              FROM {MV[0]}.{MV[1]} ORDER BY agent_code, period_month, line_of_business""")
    }
    n, stored, rounded, unrounded, off = query(conn, f"""
        SELECT COUNT(*), COALESCE(SUM(l.commission_amt), 0),
               COALESCE(SUM(ROUND({UNROUNDED}, 2)), 0), COALESCE(SUM({UNROUNDED}), 0),
               COALESCE(SUM(CASE WHEN ROUND({UNROUNDED}, 2) <> l.commission_amt THEN 1 ELSE 0 END), 0)
          FROM {LEDGER} l JOIN {RATES} r ON r.rate_id = l.rate_id""")[0]
    m["ledger_recompute"] = {
        "rows": int(n), "stored_total": _dec(stored), "rounded_total": _dec(rounded),
        "unrounded_total": _dec(unrounded), "rows_not_matching_round": int(off),
    }
    return m
