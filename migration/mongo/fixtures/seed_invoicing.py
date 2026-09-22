#!/usr/bin/env python3
"""Synthetic seed for unit `invoicing`: INVOICES + INVOICE_LINES +
CREDIT_NOTES in the LOCAL Oracle fixture only (wave-2 batch w2-b02).
Idempotent: deletes SYNTH-% rows then re-inserts.

INVOICE_LINES.invoice_id is a REAL FK (ON DELETE CASCADE): orphan lines
cannot exist here, unlike legacy-invoice-feed. Lines embed as lines[]
keyed lineNo.

Seed: invoices with 0..6 lines, NUMBER(12,2) amounts at scale edges
(0.01 / 9999999999.99 / negative-ish smalls), status codes incl.
out-of-CODES, credits partially burned (remaining < amount, some 0).

Oracle only: the seeder never writes to Mongo.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _local import require_local_dsn  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / ".migration" / "fixtures" / "w2-b02.json"

N_INVOICES = 40
N_CREDITS = 15
TENANTS = ["SYNTH-TEN-1", "SYNTH-TEN-2", "SYNTH-TEN-3"]
PERIODS = [f"SYNTH-RP-{i:04d}" for i in range(30)]
# NUMBER(12,2) scale edges
AMTS = ["0.01", "0.05", "9999999999.99", "123.45", "100.00", "0.99"]


def connection(uri: str):
    """Declares the migration target for the offline run. MongoClient is lazy
    -- this opens no socket; the seeder only ever touches Oracle."""
    from pymongo import MongoClient
    return MongoClient(uri)


def _connect():
    import oracledb
    raw = os.environ.get("ORACLE_FIXTURE_DSN")
    if not raw:
        sys.exit("ORACLE_FIXTURE_DSN not set (JSON {user,password,dsn})")
    dsn = json.loads(raw)
    require_local_dsn(dsn["dsn"])
    return oracledb.connect(user=dsn["user"], password=dsn["password"],
                            dsn=dsn["dsn"])


def _seed(conn) -> dict:
    cur = conn.cursor()
    cur.execute("DELETE FROM invoice_lines WHERE id LIKE 'SYNTH-IL-%'")
    cur.execute("DELETE FROM invoices WHERE id LIKE 'SYNTH-IV-%'")
    cur.execute("DELETE FROM credit_notes WHERE id LIKE 'SYNTH-CN-%'")

    inv_rows = []
    line_rows = []
    lid = 0
    for i in range(N_INVOICES):
        iid = f"SYNTH-IV-{i:04d}"
        inv_rows.append((
            iid,
            TENANTS[i % 3],
            PERIODS[i % len(PERIODS)],
            datetime(2026, (i % 9) + 1, (i % 27) + 1, 12, 0, 0,
                     ((i * 211) % 1000) * 1000),
            float(AMTS[i % len(AMTS)]),
            float(AMTS[(i + 1) % len(AMTS)]),
            float(AMTS[(i + 2) % len(AMTS)]),
            [0, 1, 2, 3, 55][i % 5],          # 55 = status not in CODES
        ))
        for k in range(i % 7):                # 0..6 lines per invoice
            line_rows.append((
                f"SYNTH-IL-{lid:05d}",
                iid,
                k + 1,                        # line_no (embed key)
                ["BASE", "OVER", "TAX", "ADJ"][k % 4],
                f"Line {k + 1} of invoice {i}",
                float(AMTS[(lid + k) % len(AMTS)]),
            ))
            lid += 1
    cur.executemany("INSERT INTO invoices (id,tenant_id,period_id,issued_at,subtotal,tax,total,status_cd) VALUES (:1,:2,:3,:4,:5,:6,:7,:8)", inv_rows)
    cur.executemany("INSERT INTO invoice_lines (id,invoice_id,line_no,line_type,description,amount) VALUES (:1,:2,:3,:4,:5,:6)", line_rows)

    cn_rows = []
    for i in range(N_CREDITS):
        amt = float(AMTS[(i + 3) % len(AMTS)])
        rem = [0.0, amt / 2, amt][i % 3]      # fully burned / half / untouched
        cn_rows.append((
            f"SYNTH-CN-{i:04d}",
            TENANTS[i % 3],
            dt.date(2026, (i % 9) + 1, (i % 27) + 1),
            amt,
            rem,
        ))
    cur.executemany("INSERT INTO credit_notes (id,tenant_id,issued_on,amount,remaining_amount) VALUES (:1,:2,:3,:4,:5)", cn_rows)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM invoices")
    iv = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM invoice_lines")
    il = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM credit_notes")
    cn = cur.fetchone()[0]
    counts = {"INVOICES": iv, "INVOICE_LINES": il, "CREDIT_NOTES": cn}
    print(f"invoicing: seeded {N_INVOICES} invoices, {lid} lines, "
          f"{N_CREDITS} credits (table counts {counts})")
    return counts


def _write_manifest(counts: dict) -> None:
    manifest = {
        "source": "oracle fixture FIXTURE@FREEPDB1 built from services/legacy-billing/db/oracle DDL",
        "method": "synthetic",
        "masked_columns": [],
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "produced_by": "migration/mongo/fixtures/seed_invoicing.py",
        "row_counts": counts,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {MANIFEST}")


def main() -> int:
    connection(os.environ.get(
        "MONGO_LOCAL_URI", "mongodb://127.0.0.1:27017/ow_billing_offline"))
    conn = _connect()
    counts = _seed(conn)
    conn.close()
    _write_manifest(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
