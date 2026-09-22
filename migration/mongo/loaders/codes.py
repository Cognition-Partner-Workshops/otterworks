#!/usr/bin/env python3
"""Wave 0 unit `codes`: load CODES -> codes on the local offline estate.

Reads Oracle via ORACLE_FIXTURE_DSN (JSON {"user","password","dsn"}) and writes
mongodb db `ow_billing_offline` via MONGO_LOCAL_URI. Refuses to run if
MONGODB_ATLAS_URI is set: recon_mode is offline, nothing leaves the machine.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC = REPO_ROOT / ".migration" / "03_mapping_spec.json"
TARGET_DB = "ow_billing_offline"
COLLECTIONS = ["codes"]


def _connect_oracle():
    import oracledb
    raw = os.environ.get("ORACLE_FIXTURE_DSN")
    if not raw:
        sys.exit("ORACLE_FIXTURE_DSN not set (JSON {user,password,dsn})")
    try:
        dsn = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit("ORACLE_FIXTURE_DSN must be JSON {user,password,dsn}")
    return oracledb.connect(user=dsn["user"], password=dsn["password"], dsn=dsn["dsn"])


def main() -> int:
    if os.environ.get("MONGODB_ATLAS_URI"):
        sys.exit("MONGODB_ATLAS_URI is set: offline mode refuses remote targets "
                 "(run as `env -u MONGODB_ATLAS_URI ...`)")
    uri = os.environ.get("MONGO_LOCAL_URI")
    if not uri:
        sys.exit("MONGO_LOCAL_URI not set (e.g. mongodb://127.0.0.1:27017)")
    from pymongo import MongoClient
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec_loader import load_collections
    conn = _connect_oracle()
    db = MongoClient(uri)[TARGET_DB]
    stats = load_collections(SPEC, COLLECTIONS, conn, db)
    for name, st in stats.items():
        print(f"{name}: read={st['read']} upserted={st['upserted']} "
              f"modified={st['modified']} deleted={st['deleted']} "
              f"quarantined={st['quarantined']}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
