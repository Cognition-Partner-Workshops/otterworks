"""Declare (or re-check) the freeze watermark of the legacy billing source. Read-only.

Connects as the SELECT-only role from the JSON DSN in the secret named by --source-dsn-secret
(default POSTGRESQL_RO_DSN), takes one REPEATABLE READ READ ONLY snapshot and records what
identifies the frozen state: WAL position, transaction snapshot, session time zone, and per table
the row count plus a sha256 over the rows ordered by primary key. No value from any row is written;
only hashes and counts. With --check <watermark.json> it recomputes the table counts/hashes and the
WAL position and exits 1 if anything moved.

    python .migration/recon/freeze/watermark.py --out .migration/recon/freeze/watermark.json
    python .migration/recon/freeze/watermark.py --check .migration/recon/freeze/watermark.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import psycopg

TABLES = (
    "plans", "tenants", "credit_notes", "subscriptions", "usage_events", "rating_periods",
    "rating_results", "invoices", "invoice_lines", "dunning_attempts", "notifications",
)


def table_state(cur: psycopg.Cursor, schema: str, table: str) -> dict:
    cur.execute(
        "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid"
        " AND a.attnum = ANY(i.indkey) WHERE i.indrelid = %s::regclass AND i.indisprimary"
        " ORDER BY array_position(i.indkey, a.attnum)",
        (f"{schema}.{table}",),
    )
    pk = [r[0] for r in cur.fetchall()]
    order = ", ".join(f'"{c}"' for c in pk) or "1"
    cur.execute(
        f'SELECT count(*), coalesce(string_agg(t::text, E\'\\n\' ORDER BY {order}), \'\')'
        f' FROM "{schema}"."{table}" t'
    )
    count, body = cur.fetchone()
    return {"rows": count, "pk": pk, "sha256": hashlib.sha256(body.encode()).hexdigest()}


def snapshot(dsn: dict) -> dict:
    conn = psycopg.connect(
        host=dsn["host"], port=dsn["port"], dbname=dsn["database"], user=dsn["user"],
        password=dsn["password"], autocommit=False,
    )
    schema = dsn.get("schema", "billing")
    with conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_current_wal_lsn()::text, pg_current_snapshot()::text,"
                " current_setting('TimeZone'), version(), current_user, current_database(),"
                " now() AT TIME ZONE 'UTC'"
            )
            lsn, snap, tz, version, user, db, server_now = cur.fetchone()
            tables = {t: table_state(cur, schema, t) for t in TABLES}
    conn.close()
    return {
        "source": {"database": db, "schema": schema, "role": user, "server_version": version.split(",")[0]},
        "wal_lsn": lsn,
        "txid_snapshot": snap,
        "session_timezone": tz,
        "server_now_utc": server_now.isoformat(timespec="seconds"),
        "tables": tables,
        "rows_total": sum(t["rows"] for t in tables.values()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn-secret", default="POSTGRESQL_RO_DSN")
    parser.add_argument("--out")
    parser.add_argument("--check")
    args = parser.parse_args(argv)
    dsn = json.loads(os.environ[args.source_dsn_secret])
    state = snapshot(dsn)
    if args.check:
        declared = json.load(open(args.check))
        moved = {
            t: {"declared": declared["tables"][t], "now": state["tables"][t]}
            for t in TABLES
            if (declared["tables"][t]["rows"], declared["tables"][t]["sha256"])
            != (state["tables"][t]["rows"], state["tables"][t]["sha256"])
        }
        print(json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "freeze_held": not moved, "moved": moved,
                          "wal_lsn": {"declared": declared["wal_lsn"], "now": state["wal_lsn"]},
                          "rows_total": state["rows_total"]}, indent=2))
        return 1 if moved else 0
    state = {
        "declared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_dsn_secret": args.source_dsn_secret,
        **state,
    }
    text = json.dumps(state, indent=2) + "\n"
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as handle:
            handle.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
