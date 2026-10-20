"""Copies the Commission Pay OLTP tables from Oracle (COMMISSION_PAY) into the commission schema."""
from __future__ import annotations

import datetime as dt

import psycopg

from common import oracle_connect, pg_dsn

TABLES = {
    "agents": ["agent_id", "agent_code", "full_name", "license_no", "status", "hired_date"],
    "products": ["product_code", "product_name", "line_of_business"],
    "policies": ["policy_id", "policy_no", "product_code", "holder_name", "annual_premium", "issued_date", "status"],
    "commission_rates": ["rate_id", "product_code", "agent_id", "rate_pct", "effective_from", "effective_to", "created_by"],
    "commission_splits": ["split_id", "policy_id", "agent_id", "split_pct"],
    "commission_ledger": ["ledger_id", "policy_id", "agent_id", "period_month", "rate_id", "split_pct",
                          "base_premium", "commission_amt"],
}
KEYS = {"agents": "agent_id", "products": "product_code", "policies": "policy_id", "commission_rates": "rate_id",
        "commission_splits": "split_id", "commission_ledger": "ledger_id"}


def plain(value):
    return value.date() if isinstance(value, dt.datetime) else value


def main() -> None:
    with oracle_connect() as ora, psycopg.connect(pg_dsn()) as pg:
        for table, cols in TABLES.items():
            with ora.cursor() as cur:
                cur.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY {KEYS[table]}")
                rows = [tuple(plain(v) for v in row) for row in cur]
            with pg.cursor() as cur:
                with cur.copy(f"COPY commission.{table} ({', '.join(cols)}) FROM STDIN") as copy:
                    for row in rows:
                        copy.write_row(row)
            print(f"commission.{table}: {len(rows)} rows")


if __name__ == "__main__":
    main()
