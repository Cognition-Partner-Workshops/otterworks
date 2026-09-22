#!/usr/bin/env python3
"""Synthetic seed for unit `legacy-invoice-feed`: INVOICE_HEADER + INVOICE_LINE
in the LOCAL Oracle fixture only (our copy of the source, per wave-1 batch
w1-b03). Idempotent: deletes previously-seeded SYNTH-INV ids then re-inserts.

Seed sizes per brief: 500 headers, ~4000 lines incl. 37+ orphans.

Baseline stays recon-safe: every *_dt is NULL or 'DD-MON-YY' parseable and
every gl_acct_csv is NULL or well-formed. Canon rule `date_string_to_date`
keeps unparseable strings on the source side (map-draft-3 default
`unparseable: keep`), which would be a legitimate Tier-3 FAIL rather than a
quarantine case, so dirty-date coverage comes from the fault leg and from
the REAL tenant data patterns already proven on the customers unit.

Oracle only: the seeder never writes to Mongo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _local import require_local_dsn  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / ".migration" / "fixtures" / "w1-b03.json"

N_HEADERS = 500
N_LINES = 4000
N_ORPHANS = 40

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
CUSTS = [f"SYNTH-CUST-{i:04d}" for i in range(200)]
TENANTS = ["SYNTH-TEN-1", "SYNTH-TEN-2", "SYNTH-TEN-3"]


def _hdr_id(i: int) -> str:
    return f"SYNTH-INV-{i:05d}"


def _dby(i: int):
    if i % 11 == 0:
        return None
    return f"{(i % 28) + 1:02d}-{MONTHS[i % 12]}-{(i % 24):02d}"


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
    # idempotent cleanup: synthetic ids only
    cur.execute("DELETE FROM invoice_line WHERE line_id LIKE 'SYNTH-LINE-%'")
    cur.execute("DELETE FROM invoice_header WHERE invoice_id LIKE 'SYNTH-INV-%'")

    hdr_rows = []
    for i in range(N_HEADERS):
        hdr_rows.append((
            _hdr_id(i),                     # invoice_id
            f"INV-{700000 + i}",            # invoice_no
            CUSTS[i % len(CUSTS)] if i % 9 else None,      # cust_id
            TENANTS[i % 3] if i % 13 else None,            # tenant_id
            _dby(i),                        # invoice_dt DD-MON-YY | NULL
            _dby(i + 40),                   # due_dt
            i % 4 if i % 17 else 7,         # status_cd (7 = out-of-set trap)
            float(f"{(i % 9000) / 7.0:.2f}"),  # total_amt
            1000 + (i % 12),                # batch_no
        ))
    cur.executemany("INSERT INTO invoice_header (invoice_id,invoice_no,cust_id,tenant_id,invoice_dt,due_dt,status_cd,total_amt,batch_no) VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9)", hdr_rows)

    line_rows = []
    for i in range(N_LINES):
        if i < N_ORPHANS:
            inv_ref = f"SYNTH-INV-GHOST-{i:03d}"   # orphan: no header
        else:
            inv_ref = _hdr_id(i % N_HEADERS)
        csv_i = i % 5
        gl = ([f"4000-{1000 + i % 90}", f"4000-{i % 50},6000-{i % 30}",
               None, "4100-0101", f"4000-{i % 90},5000-{i % 40},6100-{i % 20}"][csv_i])
        line_rows.append((
            f"SYNTH-LINE-{i:05d}",          # line_id
            f"INV-{700000 + (i % N_HEADERS)}",  # invoice_no (denormalised copy)
            inv_ref,                        # invoice_id (orphan for first 40)
            CUSTS[(i * 7) % 200] if i % 6 else None,   # cust_id
            f"C{9000 + i % 400}",           # cust_no
            f"Synth Customer {i % 200}",    # cust_name (copy may disagree w/ customers)
            TENANTS[i % 3] if i % 8 else None,
            (i % 900) + 1,                  # line_no
            [1, 2, 3, 99][i % 4],           # line_type_cd
            f"Item {i}",                    # item_desc
            float(f"{(i % 500) / 8.0:.3f}"),    # qty NUMBER(12,3) scale edge
            float(f"{(i % 9000) / 16.0:.4f}"),  # unit_price NUMBER(14,4)
            float(f"{(i % 99999) / 11.0:.2f}"), # amount NUMBER(14,2)
            float(f"{(i % 9999) / 13.0:.2f}"),  # tax_amt
            _dby(i * 3),                    # invoice_dt
            f"{(i % 12) + 1:02d}20{(i % 26):02d}-{(i % 12) + 1:02d}20{(i % 26):02d}" if i % 10 else None,  # service_period MMYYYY-MMYYYY
            ["Y", "N", None][i % 3],        # posted_yn
            gl,                             # gl_acct_csv
            1000 + (i % 12),                # batch_no
            ["CUSTBILL", "CONV", "LEG"][i % 3],  # src_system
        ))
    cur.executemany("INSERT INTO invoice_line (line_id,invoice_no,invoice_id,cust_id,cust_no,cust_name,tenant_id,line_no,line_type_cd,item_desc,qty,unit_price,amount,tax_amt,invoice_dt,service_period,posted_yn,gl_acct_csv,batch_no,src_system) VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13,:14,:15,:16,:17,:18,:19,:20)", line_rows)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM invoice_header")
    h = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM invoice_line")
    l = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM invoice_line WHERE invoice_id NOT IN (SELECT invoice_id FROM invoice_header)")
    o = cur.fetchone()[0]
    counts = {"INVOICE_HEADER": h, "INVOICE_LINE": l}
    print(f"legacy-invoice-feed: seeded {N_HEADERS} headers, {N_LINES} lines "
          f"({N_ORPHANS} orphans) (table counts {counts}, orphan lines {o})")
    return counts


def _write_manifest(counts: dict) -> None:
    manifest = {
        "source": "oracle fixture FIXTURE@FREEPDB1 built from services/legacy-billing/db/oracle DDL",
        "method": "synthetic",
        "masked_columns": [],
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "produced_by": "migration/mongo/fixtures/seed_legacy_invoice_feed.py",
        "row_counts": counts,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {MANIFEST}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    connection(os.environ.get(
        "MONGO_LOCAL_URI", "mongodb://127.0.0.1:27017/ow_billing_offline"))
    conn = _connect()
    counts = _seed(conn)
    conn.close()
    _write_manifest(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
