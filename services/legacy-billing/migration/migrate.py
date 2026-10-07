#!/usr/bin/env python3
"""Copy the OW_BILLING estate from Oracle into the PostgreSQL 15 target.

    make billing-pg-migrate        (Oracle and billing-pg must both be up)

Idempotent: every run truncates the target tables and reloads them in one
transaction, so a rerun leaves byte-identical table contents (recon.py
proves this by fingerprinting the target before and after a second run).

After cutover Postgres is the system of record, so a reload must not erase
writes the app made there. Each load records a fingerprint of the target;
a later run refuses to truncate when the target no longer matches it,
unless --force is given.

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
LOAD_MARK = (0, "target-fingerprint")


class TargetDiverged(RuntimeError):
    pass


def target_fingerprint(pg, include_baseline: bool = True) -> dict:
    """Content fingerprint of every target table (all columns) + sequences."""
    names = [t.name for t in estate.TABLES] + [estate.ORPHAN_TABLE]
    if include_baseline:
        names.append(estate.BASELINE_TABLE)
    fp = {}
    for name in names:
        cols = [r[0] for r in pg.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = 'ow_billing' AND table_name = %s"
            " ORDER BY ordinal_position", (name,))]
        ck = estate.SetChecksum()
        for row in pg.execute(f"SELECT {', '.join(cols)} FROM {name}"):
            ck.add_row(row)
        fp[name] = f"{ck.count}:{ck.hexdigest()}"
    for seq in estate.SEQUENCES:
        last, called = pg.execute(f"SELECT last_value, is_called FROM {seq}").fetchone()
        fp[seq] = str(last + 1 if called else last)
    return fp


def _load_digest(pg) -> str:
    fp = target_fingerprint(pg, include_baseline=False)
    return hashlib.sha256(repr(sorted(fp.items())).encode()).hexdigest()


def check_reloadable(pg) -> None:
    """Raise TargetDiverged if the target holds writes made since the last load."""
    populated = any(
        pg.execute(f"SELECT EXISTS (SELECT 1 FROM {t.name})").fetchone()[0]
        for t in estate.TABLES
    )
    if not populated:
        return
    row = pg.execute(
        f"SELECT expected FROM {estate.BASELINE_TABLE} WHERE batch_no = %s AND check_name = %s",
        LOAD_MARK,
    ).fetchone()
    if row is None or row[0] != _load_digest(pg):
        raise TargetDiverged(
            "the Postgres target has changed since the last migration load "
            "(app writes after cutover); reloading from Oracle would erase them. "
            "Rerun with --force (make billing-pg-migrate FORCE=1) only if that is intended."
        )


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


def migrate(verbose: bool = True, force: bool = False) -> dict:
    started = time.monotonic()
    summary: dict = {"tables": {}, "sequences": {}}
    with estate.oracle_connect() as ora, estate.pg_connect() as pg:
        if not force:
            check_reloadable(pg)
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
        pg.execute(
            f"INSERT INTO {estate.BASELINE_TABLE} (batch_no, check_name, expected) VALUES (%s, %s, %s)",
            (*LOAD_MARK, _load_digest(pg)),
        )
        pg.commit()
        pg.autocommit = True
        pg.execute("ANALYZE")
    summary["seconds"] = round(time.monotonic() - started, 1)
    if verbose:
        print(f"[migrate] sequences {summary['sequences']}")
        print(f"[migrate] done in {summary['seconds']}s")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true",
                    help="reload even if Postgres has writes since the last load (erases them)")
    args = ap.parse_args()
    try:
        migrate(force=args.force)
    except TargetDiverged as exc:
        print(f"[migrate] refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
