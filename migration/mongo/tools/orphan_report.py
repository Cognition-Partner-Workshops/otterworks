#!/usr/bin/env python3
"""Orphan-line report for unit `legacy-invoice-feed`: counts INVOICE_LINE
rows / legacyInvoiceLines docs whose invoiceId has no matching header, on
the Oracle fixture side and on the Mongo target side. Prints counts only.

Oracle via ORACLE_FIXTURE_DSN; Mongo via MONGO_LOCAL_URI, db
`ow_billing_offline`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "loaders"))
from spec_loader import require_local_oracle_dsn, require_local_uri  # noqa: E402


def _oracle_orphans() -> int:
    import oracledb
    dsn = json.loads(os.environ["ORACLE_FIXTURE_DSN"])
    require_local_oracle_dsn(dsn["dsn"])
    conn = oracledb.connect(user=dsn["user"], password=dsn["password"], dsn=dsn["dsn"])
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM invoice_line WHERE invoice_id NOT IN (SELECT invoice_id FROM invoice_header)")
    n = cur.fetchone()[0]
    conn.close()
    return n


def _mongo_orphans(uri: str) -> int:
    from pymongo import MongoClient
    db = MongoClient(uri)["ow_billing_offline"]
    hdrs = set()
    for d in db["legacyInvoices"].find({}, {"_id": 1}):
        hdrs.add(d["_id"])
    n = 0
    for d in db["legacyInvoiceLines"].find({}, {"invoiceId": 1}):
        if d.get("invoiceId") not in hdrs:
            n += 1
    return n


def main() -> int:
    if os.environ.get("MONGODB_ATLAS_URI"):
        sys.exit("MONGODB_ATLAS_URI is set: offline mode refuses remote targets")
    uri = os.environ.get("MONGO_LOCAL_URI")
    if not uri:
        sys.exit("MONGO_LOCAL_URI not set")
    require_local_uri(uri)
    print(f"oracle_orphan_lines={_oracle_orphans()} "
          f"mongo_orphan_lines={_mongo_orphans(uri)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
