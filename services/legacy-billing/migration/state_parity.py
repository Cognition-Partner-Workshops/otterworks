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
}
# PKG_OW_UTIL.LOG_MSG is an AUTONOMOUS_TRANSACTION on Oracle: a log row survives
# when the call that wrote it later fails. The Postgres port logs inside the
# caller's transaction. Accepted when every Postgres log row has an Oracle
# twin and the Oracle-only rows are listed.
AUDIT_LOG = "billing_audit_log"


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
    if table.name == AUDIT_LOG:
        return _audit_log(ora, pg, row)
    allowed = WALL_CLOCK.get(table.name, {})
    if o.count == p.count and row["columns"] and all(c in allowed for c in row["columns"]):
        row["result"] = "accepted difference with reason"
        row["reason"] = "; ".join(f"{c}: {allowed[c]}" for c in row["columns"])
    else:
        row["result"] = "failed"
    return row


def _audit_log(ora, pg, row: dict) -> dict:
    sql = f"SELECT module, message FROM {AUDIT_LOG}"
    o = collections.Counter(tuple(r) for r in ora_rows(ora, sql))
    p = collections.Counter(tuple(r) for r in pg.execute(sql))
    if p - o:
        row["result"] = "failed"
        row["reason"] = f"Postgres-only log rows: {dict(p - o)}"
        return row
    extra = ", ".join(f"{n} x {m}: {msg}" for (m, msg), n in sorted((o - p).items()))
    row["result"] = "accepted difference with reason"
    row["reason"] = ("every Postgres (module, message) row has an Oracle twin; log_id/logged_at are "
                     "sequence/wall-clock. Oracle-only rows come from calls that failed after "
                     "logging (LOG_MSG is autonomous on Oracle, transactional on Postgres): "
                     + (extra or "none"))
    return row


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
