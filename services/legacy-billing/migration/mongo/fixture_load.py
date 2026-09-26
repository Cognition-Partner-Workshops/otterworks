#!/usr/bin/env python3
"""Batch fixture-load step (deterministic, documented).

(w3-b01 file, shared by w3-b02; originated on branch ...--w3-b01 / PR #1725)

Loads the spec collections this batch's service code and parity replay read
into `ow_billing_migration` on the local fixture target:

    codes, plans, tenants, subscriptions, subscriptionsHist, billingAuditLog

plus the batch's declared scratch collection (emptied; `--scratch`,
default parity_w3_b02 for this branch).

Every run drops and recreates exactly those collections and re-inserts the
same deterministic documents derived from the Oracle fixture, so a re-run
yields an identical target state. Field shapes follow
`.migration/03_mapping_spec.json` (map-draft-2): natural keys, yn_to_bool,
NUMBER(12,s) -> Decimal128, DATE -> BSON datetime, empty/NULL -> absent.

One Oracle connection is shared for the whole load (source concurrency 1).
Usage (repo root, secrets by env-var NAME only):

    env -u MONGODB_ATLAS_URI OW_BILLING_FIXTURE_DSN='{...}' \
        MONGO_LOCAL_URI=mongodb://localhost:27017 \
        python3 services/legacy-billing/migration/mongo/fixture_load.py \
            --source-dsn-secret OW_BILLING_FIXTURE_DSN \
            --target-uri-secret MONGO_LOCAL_URI \
            --target-db ow_billing_migration
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
ALLOWED_TARGETS_FILE = WORKSPACE_ROOT / ".migration" / "allowed_targets.json"
BATCH_SCRATCH = "parity_w3_b02"


def _fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 2


def _secret_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(_fail(f"secret env var {name} is not set"))
    return value


def _oracle_connect(dsn_secret_name: str):
    import oracledb  # lazy: not needed for --help / allowlist failures

    raw = _secret_env(dsn_secret_name)
    try:
        conn_args = json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit(_fail(f"{dsn_secret_name} is not JSON {{user,password,dsn}}"))
    # Fetch NUMBER as decimal.Decimal so scale survives into Decimal128
    # (Oracle 49.00 must stay "49.00", not float "49.0").
    oracledb.defaults.fetch_decimals = True
    return oracledb.connect(
        user=conn_args["user"], password=conn_args["password"], dsn=conn_args["dsn"]
    )


def _s(v):
    """empty_string_is_null: '' / None -> absent."""
    if v is None or (isinstance(v, str) and v == ""):
        return None
    return str(v)


def _dec(v):
    from bson import Decimal128

    return None if v is None else Decimal128(str(v))


def _b(v):
    """yn_to_bool."""
    if v is None:
        return None
    return str(v).strip().upper() == "Y"


def _put(doc: dict, key: str, value):
    if value is not None:
        doc[key] = value


# Each loader reads its rows with an inline read-only SELECT literal (the dbx
# guard resolves `execute` arguments statically) and maps row tuples to the
# deterministic spec-shaped documents built below.
def _rows(cur, name: str, to_doc) -> list[dict]:
    if name == "codes":
        cur.execute(
            "SELECT CODE_TYPE, CODE_VAL, CODE_DESC FROM CODES "
            "ORDER BY CODE_TYPE, CODE_VAL"
        )
    elif name == "plans":
        cur.execute(
            "SELECT ID, CODE, TIER_CD, MONTHLY_FEE, INCLUDED_UNITS, "
            "OVERAGE_RATE, ACTIVE_YN FROM PLANS ORDER BY ID"
        )
    elif name == "tenants":
        cur.execute(
            "SELECT ID, NAME, TAX_EXEMPT_YN, STATUS_CD FROM TENANTS ORDER BY ID"
        )
    elif name == "subscriptions":
        cur.execute(
            "SELECT ID, TENANT_ID, PLAN_ID, STARTS_ON, ENDS_ON, STATUS_CD, "
            "SUSPENDED_ON FROM SUBSCRIPTIONS ORDER BY ID"
        )
    elif name == "subscriptionsHist":
        cur.execute(
            "SELECT HIST_ID, HIST_DT, HIST_OP, ID, TENANT_ID, PLAN_ID, "
            "STARTS_ON, ENDS_ON, STATUS_CD, SUSPENDED_ON "
            "FROM SUBSCRIPTIONS_HIST ORDER BY HIST_ID"
        )
    elif name == "billingAuditLog":
        cur.execute(
            "SELECT LOG_ID, LOGGED_AT, MODULE, MESSAGE FROM BILLING_AUDIT_LOG "
            "ORDER BY LOG_ID"
        )
    elif name == "usageEvents":
        cur.execute(
            "SELECT ID, TENANT_ID, OCCURRED_AT, UNITS, KIND_CD "
            "FROM USAGE_EVENTS ORDER BY ID"
        )
    elif name == "ratingPeriods":
        cur.execute(
            "SELECT ID, TENANT_ID, PERIOD_START, PERIOD_END "
            "FROM RATING_PERIODS ORDER BY ID"
        )
    elif name == "ratingResults":
        cur.execute(
            "SELECT ID, PERIOD_ID, SUBSCRIPTION_ID, USED_UNITS, QUOTA_UNITS, "
            "ROLLOVER_UNITS, BILLABLE_UNITS, OVERAGE_AMOUNT, CREATED_AT "
            "FROM RATING_RESULTS ORDER BY ID"
        )
    elif name == "invoices":
        cur.execute(
            "SELECT ID, TENANT_ID, PERIOD_ID, ISSUED_AT, SUBTOTAL, TAX, "
            "TOTAL, STATUS_CD FROM INVOICES ORDER BY ID"
        )
    elif name == "creditNotes":
        cur.execute(
            "SELECT ID, TENANT_ID, ISSUED_ON, AMOUNT, REMAINING_AMOUNT "
            "FROM CREDIT_NOTES ORDER BY ID"
        )
    elif name == "dunningAttempts":
        cur.execute(
            "SELECT ID, TENANT_ID, INVOICE_ID, ATTEMPT_NO, SCHEDULED_FOR, "
            "STATUS_CD FROM DUNNING_ATTEMPTS ORDER BY ID"
        )
    elif name == "notifications":
        cur.execute(
            "SELECT ID, TENANT_ID, KIND_CD, SENT_AT "
            "FROM NOTIFICATIONS ORDER BY ID"
        )
    else:
        raise ValueError(f"unknown collection {name}")
    return [to_doc(r) for r in cur]


def _code_doc(r):
    doc = {"_id": f"{r[0]}:{r[1]}", "codeType": _s(r[0]), "codeVal": int(r[1])}
    _put(doc, "codeDesc", _s(r[2]))
    return doc


def _plan_doc(r):
    doc = {"_id": _s(r[0]), "code": _s(r[1]), "tierCd": int(r[2])}
    _put(doc, "monthlyFee", _dec(r[3]))
    _put(doc, "includedUnits", None if r[4] is None else int(r[4]))
    _put(doc, "overageRate", _dec(r[5]))
    _put(doc, "active", _b(r[6]))
    return doc


def _tenant_doc(r):
    doc = {"_id": _s(r[0]), "name": _s(r[1])}
    _put(doc, "taxExempt", _b(r[2]))
    _put(doc, "statusCd", None if r[3] is None else int(r[3]))
    return doc


def _sub_doc(r):
    doc = {
        "_id": _s(r[0]),
        "tenantId": _s(r[1]),
        "planId": _s(r[2]),
        "startsOn": r[3],
        "statusCd": int(r[5]),
    }
    _put(doc, "endsOn", r[4])
    _put(doc, "suspendedOn", r[6])
    return doc


def _hist_doc(r):
    doc = {"_id": int(r[0]), "histOp": _s(r[2]), "id": _s(r[3])}
    _put(doc, "histDt", _s(r[1]))  # DD-MON-YY HH24:MI:SS text, kept verbatim
    _put(doc, "tenantId", _s(r[4]))
    _put(doc, "planId", _s(r[5]))
    _put(doc, "startsOn", r[6])
    _put(doc, "endsOn", r[7])
    _put(doc, "statusCd", None if r[8] is None else int(r[8]))
    _put(doc, "suspendedOn", r[9])
    return doc


def _audit_doc(r):
    doc = {"_id": int(r[0]), "loggedAt": r[1]}
    _put(doc, "module", _s(r[2]))
    _put(doc, "message", _s(r[3]))
    return doc


def _usage_doc(r):
    doc = {"_id": _s(r[0])}
    _put(doc, "tenantId", _s(r[1]))
    _put(doc, "occurredAt", r[2])
    _put(doc, "units", None if r[3] is None else int(r[3]))
    _put(doc, "kindCd", None if r[4] is None else int(r[4]))
    return doc


def _rperiod_doc(r):
    doc = {"_id": _s(r[0])}
    _put(doc, "tenantId", _s(r[1]))
    _put(doc, "periodStart", r[2])
    _put(doc, "periodEnd", r[3])
    return doc


def _rresult_doc(r):
    doc = {"_id": _s(r[0])}
    _put(doc, "periodId", _s(r[1]))
    _put(doc, "subscriptionId", _s(r[2]))
    _put(doc, "usedUnits", None if r[3] is None else int(r[3]))
    _put(doc, "quotaUnits", None if r[4] is None else int(r[4]))
    _put(doc, "rolloverUnits", None if r[5] is None else int(r[5]))
    _put(doc, "billableUnits", None if r[6] is None else int(r[6]))
    _put(doc, "overageAmount", _dec(r[7]))
    _put(doc, "createdAt", r[8])
    return doc


def _invoice_doc(r):
    doc = {"_id": _s(r[0]), "lines": []}
    _put(doc, "tenantId", _s(r[1]))
    _put(doc, "periodId", _s(r[2]))
    _put(doc, "issuedAt", r[3])
    _put(doc, "subtotal", _dec(r[4]))
    _put(doc, "tax", _dec(r[5]))
    _put(doc, "total", _dec(r[6]))
    _put(doc, "statusCd", None if r[7] is None else int(r[7]))
    return doc


def _credit_doc(r):
    doc = {"_id": _s(r[0])}
    _put(doc, "tenantId", _s(r[1]))
    _put(doc, "issuedOn", r[2])
    _put(doc, "amount", _dec(r[3]))
    _put(doc, "remainingAmount", _dec(r[4]))
    return doc


def _attempt_doc(r):
    doc = {"_id": _s(r[0])}
    _put(doc, "tenantId", _s(r[1]))
    _put(doc, "invoiceId", _s(r[2]))
    _put(doc, "attemptNo", None if r[3] is None else int(r[3]))
    _put(doc, "scheduledFor", r[4])
    _put(doc, "statusCd", None if r[5] is None else int(r[5]))
    return doc


def _notif_doc(r):
    doc = {"_id": _s(r[0])}
    _put(doc, "tenantId", _s(r[1]))
    _put(doc, "kindCd", None if r[2] is None else int(r[2]))
    _put(doc, "sentAt", r[3])
    return doc


LOADERS = {
    "codes": _code_doc,
    "plans": _plan_doc,
    "tenants": _tenant_doc,
    "subscriptions": _sub_doc,
    "subscriptionsHist": _hist_doc,
    "billingAuditLog": _audit_doc,
    "usageEvents": _usage_doc,
    "ratingPeriods": _rperiod_doc,
    "ratingResults": _rresult_doc,
    "invoices": _invoice_doc,
    "creditNotes": _credit_doc,
    "dunningAttempts": _attempt_doc,
    "notifications": _notif_doc,
}


def load_baseline(conn, db, collections=None, scratch=BATCH_SCRATCH) -> dict:
    """Drop+recreate the used collections (+batch scratch), reload baseline.

    Returns {collection: loaded_count}. Deterministic: same source -> same
    documents, every run.
    """
    from pymongo.errors import PyMongoError  # noqa: F401  (import check)

    names = list(collections or LOADERS.keys())
    counts = {}
    for name in names:
        to_doc = LOADERS[name]
        cur = conn.cursor()
        docs = _rows(cur, name, to_doc)
        if name == "invoices":
            # INVOICE_LINES embeds under the parent document as `lines`,
            # ordered by line_no (mapping spec, invoices.lines embed).
            by_inv = {}
            cur.execute(
                "SELECT ID, INVOICE_ID, LINE_NO, LINE_TYPE, DESCRIPTION, "
                "AMOUNT FROM INVOICE_LINES ORDER BY INVOICE_ID, LINE_NO"
            )
            for lid, inv_id, lno, ltype, descr, amt in cur:
                line = {"id": _s(lid), "lineNo": int(lno)}
                _put(line, "lineType", _s(ltype))
                _put(line, "description", _s(descr))
                _put(line, "amount", _dec(amt))
                by_inv.setdefault(inv_id, []).append(line)
            for doc in docs:
                doc["lines"] = by_inv.get(doc["_id"], [])
        cur.close()
        db.drop_collection(name)
        if docs:
            db[name].insert_many(docs, ordered=True)
        counts[name] = len(docs)
    db.drop_collection(scratch)
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-dsn-secret", required=True)
    ap.add_argument("--target-uri-secret", required=True)
    ap.add_argument("--target-db", required=True)
    ap.add_argument("--scratch", default=BATCH_SCRATCH)
    args = ap.parse_args()

    allowed = json.loads(ALLOWED_TARGETS_FILE.read_text())
    if args.target_db not in allowed.get("databases", []):
        return _fail(
            f"target-db {args.target_db!r} not in {ALLOWED_TARGETS_FILE} "
            f"databases {allowed.get('databases')}"
        )

    from pymongo import MongoClient

    conn = _oracle_connect(args.source_dsn_secret)
    try:
        client = MongoClient(_secret_env(args.target_uri_secret),
                             serverSelectionTimeoutMS=5000)
        try:
            counts = load_baseline(conn, client[args.target_db], scratch=args.scratch)
        finally:
            client.close()
    finally:
        conn.close()

    print(json.dumps({"batch": args.scratch, "target": args.target_db,
                      "loaded": counts, "scratch": args.scratch}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
