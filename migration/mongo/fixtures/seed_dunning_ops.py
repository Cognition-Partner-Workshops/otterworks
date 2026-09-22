#!/usr/bin/env python3
"""Synthetic seed for unit `dunning-ops`: DUNNING_ATTEMPTS + NOTIFICATIONS +
BILLING_AUDIT_LOG in the LOCAL Oracle fixture only (wave-2 batch w2-b03).
Idempotent: deletes SYNTH-% rows then re-inserts.

Constraints honoured: UQ_DUNNING_ATTEMPTS (invoice_id, attempt_no),
UQ_NOTIFICATIONS (tenant_id, kind_cd, sent_at) -- the natural dedupe key,
FKs to tenants/invoices, trg_billing_audit_log_id fills NULL log_id.

Seed: attempts across statuses and attempt_no; notifications exercising
the dedupe key; audit rows with 4000-char messages, NULL module, loggedAt
within 90 days (TTL index replaces JOB_PURGE_AUDIT_LOG; see notes).

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
MANIFEST = REPO_ROOT / ".migration" / "fixtures" / "w2-b03.json"

TENANTS = ["SYNTH-TEN-1", "SYNTH-TEN-2", "SYNTH-TEN-3"]
INVOICES = [f"SYNTH-IV-{i:04d}" for i in range(40)]


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
    cur.execute("DELETE FROM dunning_attempts WHERE id LIKE 'SYNTH-DA-%'")
    cur.execute("DELETE FROM notifications WHERE id LIKE 'SYNTH-NT-%'")
    cur.execute("DELETE FROM billing_audit_log WHERE log_id >= 8800000")

    today = dt.date(2026, 9, 22)
    da_rows = []
    aid = 0
    for i in range(30):
        for a in range(1 + (i % 3)):         # 1-3 attempts per invoice
            da_rows.append((
                f"SYNTH-DA-{aid:04d}",
                TENANTS[i % 3],
                INVOICES[i],
                a + 1,                        # attempt_no 1..3 (UQ pair)
                today - dt.timedelta(days=(aid % 40) + 1),
                [1, 2, 3, 9][a % 4],          # status spread (DUN_STATUS)
            ))
            aid += 1
    cur.executemany("INSERT INTO dunning_attempts (id,tenant_id,invoice_id,attempt_no,scheduled_for,status_cd) VALUES (:1,:2,:3,:4,:5,:6)", da_rows)

    nt_rows = []
    for i in range(20):
        nt_rows.append((
            f"SYNTH-NT-{i:04d}",
            TENANTS[i % 3],
            (i % 4) + 1,                      # kind_cd (NOTIF_KIND)
            # sent_at spread: unique (tenant, kind, sent_at) triples
            datetime(2026, 9, 20, i % 24, i % 60, i, (i % 1000) * 1000),
        ))
    cur.executemany("INSERT INTO notifications (id,tenant_id,kind_cd,sent_at) VALUES (:1,:2,:3,:4)", nt_rows)

    bal_rows = []
    for i in range(15):
        bal_rows.append((
            8800000 + i,                      # explicit log_id band
            dt.date(2026, 7, 1) + dt.timedelta(days=i),   # within 90 days
            ["RATING", "INVOICING", "DUNNING", "UTIL", None][i % 5],
            ("audit message %d " % i + "x" * 4000)[:4000],  # 4000-char edge
        ))
    cur.executemany("INSERT INTO billing_audit_log (log_id,logged_at,module,message) VALUES (:1,:2,:3,:4)", bal_rows)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM dunning_attempts")
    da = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM notifications")
    nt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM billing_audit_log")
    bal = cur.fetchone()[0]
    counts = {"DUNNING_ATTEMPTS": da, "NOTIFICATIONS": nt,
              "BILLING_AUDIT_LOG": bal}
    print(f"dunning-ops: seeded {aid} attempts, 20 notifications, "
          f"15 audit rows (table counts {counts})")
    return counts


def _write_manifest(counts: dict) -> None:
    manifest = {
        "source": "oracle fixture FIXTURE@FREEPDB1 built from services/legacy-billing/db/oracle DDL",
        "method": "synthetic",
        "masked_columns": [],
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "produced_by": "migration/mongo/fixtures/seed_dunning_ops.py",
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
