#!/usr/bin/env python3
"""Copy the OW_BILLING estate from Oracle into the PostgreSQL 15 target.

    make billing-pg-migrate        (Oracle and billing-pg must both be up)

Idempotent: every run truncates the target tables and reloads them in one
transaction, so a rerun leaves byte-identical table contents (recon.py
proves this by fingerprinting the target before and after a second run).

Bulk INVOICE_LINE rows whose invoice_id has no INVOICE_HEADER row are not
loaded into invoice_line (which now has a real FK). They are copied
unchanged into invoice_line_orphan with a quarantine_reason, so nothing is
dropped and month-end joins see exactly the rows Oracle's inner join saw.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import estate  # noqa: E402

FETCH = 5000


def _converter(column: estate.Column):
    if column.data_type == "date":
        def to_date(value):
            if isinstance(value, datetime):
                if value.time() != dtime.min:
                    raise ValueError(f"{column.name}: Oracle DATE {value} has a time part")
                return value.date()
            return value
        return to_date
    return None


def copy_table(ora, pg, table: estate.Table, header_ids: set[str] | None) -> dict:
    columns = estate.pg_columns(pg, table.name)
    names = [c.name for c in columns]
    oracle_names = estate.oracle_columns(ora, table.name)
    if sorted(names) != sorted(oracle_names):
        raise SystemExit(
            f"{table.name}: column mismatch oracle={sorted(set(oracle_names) - set(names))} "
            f"postgres={sorted(set(names) - set(oracle_names))}"
        )
    converters = [_converter(c) for c in columns]
    col_list = ", ".join(names)
    invoice_idx = names.index("invoice_id") if table.split else None
    counts = {"source": 0, table.name: 0}
    if table.split:
        counts[estate.ORPHAN_TABLE] = 0

    with ora.cursor() as cur:
        cur.arraysize = FETCH
        cur.prefetchrows = FETCH + 1
        cur.execute(f"SELECT {col_list} FROM {table.name} ORDER BY {', '.join(table.key)}")
        orphans = []
        with pg.cursor().copy(f"COPY {table.name} ({col_list}) FROM STDIN") as copy:
            while True:
                batch = cur.fetchmany()
                if not batch:
                    break
                for raw in batch:
                    row = [conv(v) if conv else v for conv, v in zip(converters, raw)]
                    counts["source"] += 1
                    if table.split:
                        invoice_id = row[invoice_idx]
                        if invoice_id is None:
                            orphans.append(row + [estate.NULL_INVOICE_REASON])
                            continue
                        if invoice_id not in header_ids:
                            orphans.append(row + [estate.ORPHAN_REASON])
                            continue
                    copy.write_row(row)
                    counts[table.name] += 1
        if orphans:
            with pg.cursor().copy(
                f"COPY {estate.ORPHAN_TABLE} ({col_list}, quarantine_reason) FROM STDIN"
            ) as copy:
                for row in orphans:
                    copy.write_row(row)
            counts[estate.ORPHAN_TABLE] = len(orphans)
    return counts


def sync_sequences(ora, pg) -> dict:
    with ora.cursor() as cur:
        cur.execute("SELECT LOWER(sequence_name), last_number FROM user_sequences")
        oracle_next = {name: int(last) for name, last in cur}
    synced = {}
    for name in estate.SEQUENCES:
        # Oracle LAST_NUMBER is the next value it would hand out (the cache
        # high-water mark for cached sequences), so it never collides.
        pg.execute("SELECT setval(%s, %s, false)", (name, oracle_next[name]))
        synced[name] = oracle_next[name]
    return synced


MONEY = "'FM999999999999990.00'"
BASELINE_SQL = {
    "customers": f"""
        SELECT conversion_batch_no, COUNT(*), TO_CHAR(SUM(cur_bal_amt), {MONEY}),
               TO_CHAR(SUM(past_due_amt), {MONEY})
          FROM customer_master WHERE conversion_batch_no IS NOT NULL
         GROUP BY conversion_batch_no""",
    "headers": f"""
        SELECT batch_no, COUNT(*), TO_CHAR(SUM(total_amt), {MONEY})
          FROM invoice_header WHERE batch_no IS NOT NULL GROUP BY batch_no""",
    "lines": f"""
        SELECT l.batch_no, COUNT(*), TO_CHAR(SUM(l.amount), {MONEY}),
               TO_CHAR(SUM(l.tax_amt), {MONEY}),
               SUM(CASE WHEN h.invoice_id IS NULL THEN 1 ELSE 0 END),
               TO_CHAR(SUM(CASE WHEN h.invoice_id IS NULL THEN l.amount END), {MONEY})
          FROM invoice_line l LEFT JOIN invoice_header h ON h.invoice_id = l.invoice_id
         WHERE l.batch_no IS NOT NULL GROUP BY l.batch_no""",
}


def capture_baseline(ora) -> list[tuple[int, str, str | None]]:
    """Oracle-side per-batch figures that /api/reports/reconciliation later
    recomputes from Postgres (drift detection once Oracle is gone)."""
    out: list[tuple[int, str, str | None]] = []
    with ora.cursor() as cur:
        cur.execute(BASELINE_SQL["customers"])
        for batch, count, balance, past_due in cur.fetchall():
            out += [(batch, "customers-count", str(count)),
                    (batch, "current-balance-total", balance),
                    (batch, "past-due-total", past_due)]
        digests: dict[int, list[tuple[str, str]]] = {}
        cur.execute("SELECT conversion_batch_no, cust_id, cur_bal_amt FROM customer_master"
                    " WHERE conversion_batch_no IS NOT NULL")
        for batch, cust_id, balance in cur:
            digests.setdefault(batch, []).append((cust_id, f"{balance:.2f}"))
        for batch, pairs in digests.items():
            h = hashlib.md5()
            for cust_id, balance in sorted(pairs):
                h.update(f"{cust_id}:{balance}\n".encode())
            out.append((batch, "customers-checksum", h.hexdigest()))
        cur.execute(BASELINE_SQL["headers"])
        for batch, count, total in cur.fetchall():
            out += [(batch, "invoice-headers-count", str(count)),
                    (batch, "invoice-header-total", total)]
        cur.execute(BASELINE_SQL["lines"])
        for batch, count, amount, tax, orphans, orphan_amount in cur.fetchall():
            out += [(batch, "invoice-lines-count", str(count)),
                    (batch, "invoice-line-amount", amount),
                    (batch, "invoice-line-tax", tax),
                    (batch, "orphan-lines-quarantined", str(orphans)),
                    (batch, "orphan-line-amount", orphan_amount)]
    return out


def migrate(verbose: bool = True) -> dict:
    started = time.monotonic()
    summary: dict = {"tables": {}, "sequences": {}}
    with estate.oracle_connect() as ora, estate.pg_connect() as pg:
        all_tables = [t.name for t in estate.TABLES] + [estate.ORPHAN_TABLE, estate.BASELINE_TABLE]
        pg.execute("TRUNCATE " + ", ".join(all_tables))
        # Row triggers (sequence fillers, history copies, usage checks) must
        # not rewrite migrated rows. FK constraint triggers stay enabled, so
        # fk_invoice_line_header is enforced during the load.
        for name in all_tables:
            pg.execute(f"ALTER TABLE {name} DISABLE TRIGGER USER")
        header_ids: set[str] | None = None
        for table in estate.TABLES:
            if table.split:
                header_ids = {
                    row[0] for row in pg.execute("SELECT invoice_id FROM invoice_header")
                }
            counts = copy_table(ora, pg, table, header_ids)
            summary["tables"][table.name] = counts
            if verbose:
                split = ""
                if table.split:
                    split = f" = {counts[table.name]} + {counts[estate.ORPHAN_TABLE]} quarantined"
                print(f"[migrate] {table.name:<22} {counts['source']:>7}{split}")
        summary["sequences"] = sync_sequences(ora, pg)
        baseline = capture_baseline(ora)
        with pg.cursor().copy(
            f"COPY {estate.BASELINE_TABLE} (batch_no, check_name, expected) FROM STDIN"
        ) as copy:
            for row in baseline:
                copy.write_row(row)
        summary["baseline_rows"] = len(baseline)
        for name in all_tables:
            pg.execute(f"ALTER TABLE {name} ENABLE TRIGGER USER")
        pg.commit()
        pg.autocommit = True
        pg.execute("ANALYZE")
    summary["seconds"] = round(time.monotonic() - started, 1)
    if verbose:
        print(f"[migrate] sequences {summary['sequences']}")
        print(f"[migrate] done in {summary['seconds']}s")
    return summary


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    migrate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
