#!/usr/bin/env python3
"""Synthetic CODES rows for the w0-b01 fixture (LOCAL ORACLE FIXTURE ONLY).

The fixture already carries the static CODES rows loaded by the estate DDL
(schema/01_tables.sql). This seed adds synthetic rows that exercise the census
traps reachable on CODES (trap: reference_data; the DDL gives CODE_DESC NOT
NULL so empty-string/NULL descriptions cannot be planted):

- unknown code values / types no package decodes ('SYNTH_KIND', 'XX_STATUS')
- high-band code vals (90/99) like the estate's UNKNOWN(<cd>) path sees
- CHAR/VARCHAR2 padding: 'SYNTH_PAD ' (trailing space in the key) and a
  padded description, and a whitespace-only description
- a VARCHAR2 key that differs only by trailing padding from its sibling

Idempotent: MERGE on the (code_type, code_val) PK, re-runnable. Writes the
batch fixture manifest .migration/fixtures/w0-b01.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / ".migration" / "fixtures" / "w0-b01.json"

SYNTHETIC_ROWS = [
    # (code_type, code_val, code_desc)
    ("SYNTH_KIND", 1, "synthetic alpha"),
    ("SYNTH_KIND", 2, "synthetic beta"),
    ("SYNTH_KIND", 90, "high-band synthetic"),
    ("SYNTH_KIND", 99, "unknown-slot synthetic"),
    ("XX_STATUS", 1, "unreferenced status"),
    ("SYNTH_PAD", 1, "padded-key sibling"),
    ("SYNTH_PAD ", 1, "trailing-space key"),        # key differs only by padding
    ("SYNTH_PAD", 2, "  padded description  "),     # spaces around the value
    ("SYNTH_PAD", 3, "   "),                        # whitespace-only description
]


def connection(uri: str):
    """Mongo target handle; the URI carries the declared database."""
    from pymongo import MongoClient
    return MongoClient(uri)


def _connect(dsn_override=None):
    import oracledb
    raw = os.environ.get("ORACLE_FIXTURE_DSN")
    if not raw:
        sys.exit("ORACLE_FIXTURE_DSN not set (JSON {user,password,dsn})")
    dsn = json.loads(raw)
    easy = dsn_override or dsn["dsn"]
    if not easy.startswith(("127.0.0.1", "localhost")):
        sys.exit("offline fixture must be local (127.0.0.1 or localhost)")
    return oracledb.connect(user=dsn["user"], password=dsn["password"],
                            dsn=easy)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=None,
                    help="override the dsn field of ORACLE_FIXTURE_DSN "
                         "(spell the fixture host out, e.g. 127.0.0.1:1521/FREEPDB1)")
    args = ap.parse_args()
    target = connection(os.environ.get(
        "MONGO_LOCAL_URI", "mongodb://127.0.0.1:27017/ow_billing_offline"))
    target.admin.command("ping")  # fixture target must be reachable before seeding
    conn = _connect(args.dsn)
    cur = conn.cursor()
    for row in SYNTHETIC_ROWS:
        cur.execute(
            """MERGE INTO codes c
               USING (SELECT :1 code_type, :2 code_val, :3 code_desc FROM dual) s
               ON (c.code_type = s.code_type AND c.code_val = s.code_val)
               WHEN MATCHED THEN UPDATE SET c.code_desc = s.code_desc
               WHEN NOT MATCHED THEN INSERT VALUES (s.code_type, s.code_val, s.code_desc)""",
            row,
        )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM codes")
    total = cur.fetchone()[0]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "source": "oracle fixture FIXTURE@FREEPDB1 built from services/legacy-billing/db/oracle DDL",
        "method": "synthetic",
        "masked_columns": [],
        "produced_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "produced_by": "migration/mongo/fixtures/seed_codes.py",
        "row_counts": {"CODES": total},
    }, indent=2) + "\n")
    print(f"codes: seeded {len(SYNTHETIC_ROWS)} synthetic rows (table now {total})")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
