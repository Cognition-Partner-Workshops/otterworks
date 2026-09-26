#!/usr/bin/env python3
"""Unit u-00-codes loader: OW_BILLING.CODES -> ow_billing_migration.codes.

Offline engagement (source_access=ddl_only, target_access=local). Reads the
same-engine synthetic Oracle fixture via the DSN named by --source-dsn-secret
and bulk-loads the `codes` reference collection on a local MongoDB.

Shape is fixed by .migration/03_mapping_spec.json (map-draft-2), collection
`codes`: composite natural key CODE_TYPE/CODE_VAL -> codeType/codeVal,
CODE_DESC -> codeDesc (string, empty_string_is_null). The mapping spec's
`canonicalization` also declares `null_missing_equiv`, so fields whose value
is NULL (after rules) are stored as absent.

Run (from repo root, secrets passed by env-var NAME only):

    env -u MONGODB_ATLAS_URI OW_BILLING_FIXTURE_DSN='{...}' \
        MONGO_LOCAL_URI=mongodb://localhost:27017 \
        python3 services/legacy-billing/migration/mongo/load_codes.py \
            --source-dsn-secret OW_BILLING_FIXTURE_DSN \
            --target-uri-secret MONGO_LOCAL_URI \
            --target-db ow_billing_migration

Idempotent: the run drops and recreates only `codes` and re-inserts the same
deterministic documents, so a re-run yields an identical collection.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import oracledb
from pymongo import MongoClient

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
ALLOWED_TARGETS_FILE = WORKSPACE_ROOT / ".migration" / "allowed_targets.json"
TARGET_COLLECTION = "codes"
QUARANTINE_DETAIL_CAP = 100


def _fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 2


def _secret_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(_fail(f"secret env var {name} is not set"))
    return value


def canonicalize_code(row):
    """Return (doc, quarantine_reason) for one CODES row.

    doc is None when quarantined. Rules from the mapping spec:
    codeType/codeDesc: empty_string_is_null; codeVal: raw (bson long).
    """
    code_type, code_val, code_desc = row
    if code_type is None or str(code_type).strip() == "":
        return None, "empty_string_is_null:CODE_TYPE"
    if code_val is None:
        return None, "null_key:CODE_VAL"
    doc = {"codeType": str(code_type), "codeVal": int(code_val)}
    if code_desc is not None and str(code_desc) != "":
        doc["codeDesc"] = str(code_desc)
    # _id: deterministic surrogate over the natural key so re-runs and
    # duplicate source rows converge on one document.
    doc["_id"] = f"{doc['codeType']}:{doc['codeVal']}"
    return doc, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-dsn-secret", required=True,
                    help="env var NAME holding the source DSN (JSON or user/pass@dsn)")
    ap.add_argument("--target-uri-secret", required=True,
                    help="env var NAME holding the MongoDB URI")
    ap.add_argument("--target-db", required=True)
    args = ap.parse_args()

    allowed = json.loads(ALLOWED_TARGETS_FILE.read_text())
    if args.target_db not in allowed.get("databases", []):
        return _fail(
            f"target-db {args.target_db!r} not in {ALLOWED_TARGETS_FILE} "
            f"databases {allowed.get('databases')}"
        )

    dsn_raw = _secret_env(args.source_dsn_secret)
    try:
        conn_args = json.loads(dsn_raw)
    except json.JSONDecodeError:
        return _fail(f"{args.source_dsn_secret} is not JSON {{user,password,dsn}}")
    uri = _secret_env(args.target_uri_secret)

    docs = []
    quarantine = {}
    quarantine_rows = []
    seen_keys = set()
    with oracledb.connect(
        user=conn_args["user"],
        password=conn_args["password"],
        dsn=conn_args["dsn"],
    ) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT CODE_TYPE, CODE_VAL, CODE_DESC FROM CODES "
            "ORDER BY CODE_TYPE, CODE_VAL"
        )
        for row in cur:
            doc, reason = canonicalize_code(row)
            if doc is None:
                quarantine[reason] = quarantine.get(reason, 0) + 1
                if len(quarantine_rows) < QUARANTINE_DETAIL_CAP:
                    quarantine_rows.append({"row": [str(v) for v in row],
                                            "reason": reason})
                continue
            key = doc["_id"]
            if key in seen_keys:
                quarantine["duplicate_key"] = quarantine.get("duplicate_key", 0) + 1
                continue
            seen_keys.add(key)
            docs.append(doc)

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        db = client[args.target_db]
        db.drop_collection(TARGET_COLLECTION)
        if docs:
            db[TARGET_COLLECTION].insert_many(docs, ordered=True)
    finally:
        client.close()

    summary = {
        "unit": "u-00-codes",
        "source": "OW_BILLING.CODES",
        "target": f"{args.target_db}.{TARGET_COLLECTION}",
        "loaded": len(docs),
        "quarantined": sum(quarantine.values()),
        "quarantine_reasons": quarantine,
        "quarantine_detail_cap": QUARANTINE_DETAIL_CAP,
    }
    if quarantine_rows:
        summary["quarantine_rows"] = quarantine_rows
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
