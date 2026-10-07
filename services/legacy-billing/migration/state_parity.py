#!/usr/bin/env python3
"""After the characterization scenario has run on both engines, compare the
resulting estate table by table (row count + all-column checksum).

Oracle got the writes through the Oracle-backed app, Postgres through the
Postgres-backed app, both from the same migrated starting point. Columns that
differ are listed; wall-clock columns are expected to differ and are named in
WALL_CLOCK with the reason.

    python state_parity.py [--out <md>]
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

import estate
from recon import checksum_rows, ora_rows

# table -> {column: reason}
WALL_CLOCK = {
    "subscriptions_hist": {"hist_dt": "SYSDATE / now() at write time"},
    "billing_audit_log": {"logged_at": "SYSDATE / LOCALTIMESTAMP at write time"},
}


def _sources(table: estate.Table) -> list[str]:
    return [table.name, estate.ORPHAN_TABLE] if table.split else [table.name]


def _pg_checksum(pg, table, cols):
    ck = None
    for name in _sources(table):
        part = checksum_rows(pg.execute(f"SELECT {', '.join(cols)} FROM {name}"))
        ck = part if ck is None else ck.merge(part)
    return ck


def compare(ora, pg, table: estate.Table) -> dict:
    cols = estate.oracle_columns(ora, table.name)
    o = checksum_rows(ora_rows(ora, f"SELECT {', '.join(cols)} FROM {table.name}"))
    p = _pg_checksum(pg, table, cols)
    row = {"table": table.name, "oracle": o.count, "postgres": p.count, "columns": []}
    if o.count == p.count and o.hexdigest() == p.hexdigest():
        row["result"] = "identical"
        return row
    for col in cols:
        oc = checksum_rows(ora_rows(ora, f"SELECT {col} FROM {table.name}"))
        pc = _pg_checksum(pg, table, [col])
        if oc.hexdigest() != pc.hexdigest():
            row["columns"].append(col)
    allowed = WALL_CLOCK.get(table.name, {})
    if o.count == p.count and row["columns"] and all(c in allowed for c in row["columns"]):
        row["result"] = "accepted difference with reason"
        row["reason"] = "; ".join(f"{c}: {allowed[c]}" for c in row["columns"])
    else:
        row["result"] = "failed"
        row["reason"] = _row_diff(ora, pg, table, [c for c in cols if c not in allowed])
    return row


def _row_diff(ora, pg, table: estate.Table, cols: list[str]) -> str:
    """Rows (on the non-wall-clock columns) present on one engine only."""
    sql = f"SELECT {', '.join(cols)} FROM "
    o = collections.Counter(tuple(r) for r in ora_rows(ora, sql + table.name))
    p = collections.Counter()
    for name in _sources(table):
        p.update(tuple(r) for r in pg.execute(sql + name))
    def fmt(c):
        return "; ".join(f"{n} x {row}" for row, n in sorted(c.items(), key=str)[:10]) or "none"
    return f"Oracle-only rows: {fmt(o - p)}. Postgres-only rows: {fmt(p - o)}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    with estate.oracle_connect() as ora, estate.pg_connect() as pg:
        results = [compare(ora, pg, t) for t in estate.TABLES]
    lines = ["| Table | Oracle rows | Postgres rows | Result | Detail |",
             "| --- | ---: | ---: | --- | --- |"]
    for r in results:
        detail = r.get("reason") or (f"differs in {', '.join(r['columns'])}" if r["columns"] else
                                     "all columns, order-independent checksum")
        lines.append(f"| {r['table']} | {r['oracle']} | {r['postgres']} | {r['result']} | {detail} |")
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)
    return 1 if any(r["result"] == "failed" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
