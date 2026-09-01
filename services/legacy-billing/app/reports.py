"""Month-end finance reporting served from MongoDB, with Oracle reconciliation.

The report is the legacy RPT-114 rollup (see
db/oracle/ops/OPERATIONS_HANDBOOK.doc.txt and the CODES lookup conventions):
invoice counts and header totals by status, plus a line rollup by status and
line type. Orphaned invoice feed rows are quarantined and therefore fall out of
the embedded-line rollup, exactly as finance always ran it. Rows are
namespace-scoped through the deterministic conversion batch number.
"""

import hashlib
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

from bson import Decimal128
from flask import Blueprint, jsonify, request
from pymongo import MongoClient

reports = Blueprint("reports", __name__)
logger = logging.getLogger(__name__)

ESTATE_UNAVAILABLE = {
    "error": "legacy estate unavailable",
    "detail": "the Oracle billing estate is not reachable; try again later",
}

SOURCE = {
    "engine": "oracle",
    "system": "OW_BILLING legacy estate (Oracle FREEPDB1)",
    "detail": "INVOICE_HEADER / INVOICE_LINE via CODES lookup (RPT-114)",
}

MONGO_SOURCE = {
    "engine": "mongodb",
    "system": "MongoDB Atlas ow_tp_mongodb_205236",
    "detail": "invoices (lines[] embedded) with codes lookup (RPT-114)",
}
MIGRATION_NS = "mongo_205236"
LINE_TYPES = {1: "CHARGE", 2: "CREDIT", 3: "ADJUSTMENT", 9: "MISC"}
_MONGO_CLIENT = None

BALANCES_SQL = """
SELECT COUNT(*)                                          AS customer_count,
       TO_CHAR(SUM(cur_bal_amt), 'FM999999999999990.00') AS current_balance_total,
       TO_CHAR(SUM(past_due_amt), 'FM999999999999990.00') AS past_due_total
  FROM customer_master
 WHERE conversion_batch_no = :batch_no
"""


def ns_batch_no(ns):
    """Deterministic conversion batch number for a namespace.

    Mirrors testdata/legacy/legacy_common.ns_seed + oracle_billing_seed:
    sha256(ns)[:8] as int, folded into the 8-digit NUMBER(8) batch range.
    """
    seed = int(hashlib.sha256(ns.encode()).hexdigest()[:8], 16)
    return seed % 90_000_000 + 1_000_000


def shape_status_rows(rows):
    return [
        {"status": status, "invoice_count": count, "header_total_amt": total}
        for status, count, total in rows
    ]


def shape_line_rows(rows):
    return [
        {
            "status": status,
            "line_type": line_type,
            "line_count": line_count,
            "line_amount": line_amount,
            "line_tax": line_tax,
            "invoices_touched": invoices_touched,
        }
        for status, line_type, line_count, line_amount, line_tax, invoices_touched in rows
    ]


def shape_balances(row):
    customer_count, current_total, past_due_total = row
    return {
        "customer_count": customer_count,
        "current_balance_total": current_total,
        "past_due_total": past_due_total,
    }


def oracle_connect():
    import oracledb

    return oracledb.connect(
        user=os.getenv("ORACLE_USER", "ow_billing"),
        password=os.getenv("ORACLE_PASSWORD", "ow_billing"),
        host=os.getenv("ORACLE_HOST", "localhost"),
        port=int(os.getenv("ORACLE_PORT", "52521")),
        service_name=os.getenv("ORACLE_SERVICE", "FREEPDB1"),
    )


def oracle_query(sql, params):
    with oracle_connect() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def report_meta(ns, source=SOURCE):
    return {
        "namespace": ns,
        "batch_no": ns_batch_no(ns),
        "source": source,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def mongo_db():
    global _MONGO_CLIENT
    if _MONGO_CLIENT is None:
        _MONGO_CLIENT = MongoClient(
            os.environ["MONGODB_ATLAS_URI"],
            serverSelectionTimeoutMS=int(os.getenv("MONGODB_TIMEOUT_MS", "5000")),
        )
    return _MONGO_CLIENT[os.getenv("MONGODB_DB", "ow_tp_mongodb_205236")]


def status_desc(codes, cd):
    return codes.get(cd) or f"UNKNOWN({'' if cd is None else cd})"


def line_type(cd):
    return LINE_TYPES.get(cd) or f"UNKNOWN({'' if cd is None else cd})"


def fmt_amt(value):
    if value is None:
        return None
    if isinstance(value, Decimal128):
        value = value.to_decimal()
    return f"{value:.2f}"


def inv_status_codes(db):
    return {
        document["code_val"]: document["code_desc"]
        for document in db.codes.find(
            {"code_type": "INV_STATUS"}, {"code_val": 1, "code_desc": 1}
        )
    }


def _amount_total(value, nonnull):
    return fmt_amt(value if nonnull else None)


def status_rows_mongo(db, batch_no):
    codes = inv_status_codes(db)
    grouped = {}
    pipeline = [
        {"$match": {"ns": MIGRATION_NS, "batch_no": batch_no}},
        {
            "$group": {
                "_id": "$status_cd",
                "invoice_count": {"$sum": 1},
                "header_total_amt": {"$sum": "$total_amt"},
                "nonnull": {
                    "$sum": {
                        "$cond": [{"$ne": ["$total_amt", None]}, 1, 0]
                    }
                },
            }
        },
    ]
    for item in db.invoices.aggregate(pipeline):
        status = status_desc(codes, item["_id"])
        existing = grouped.setdefault(
            status, {"count": 0, "total": Decimal(0), "nonnull": 0}
        )
        existing["count"] += item["invoice_count"]
        existing["nonnull"] += item["nonnull"]
        if item["nonnull"]:
            total = item["header_total_amt"]
            if isinstance(total, Decimal128):
                total = total.to_decimal()
            existing["total"] += total
    return [
        (
            status,
            values["count"],
            _amount_total(values["total"], values["nonnull"]),
        )
        for status, values in sorted(grouped.items())
    ]


def line_rows_mongo(db, batch_no):
    codes = inv_status_codes(db)
    grouped = {}
    pipeline = [
        {"$match": {"ns": MIGRATION_NS, "batch_no": batch_no}},
        {"$unwind": "$lines"},
        {
            "$group": {
                "_id": {"s": "$status_cd", "t": "$lines.line_type_cd"},
                "line_count": {"$sum": 1},
                "line_amount": {"$sum": "$lines.amount"},
                "amount_nonnull": {
                    "$sum": {
                        "$cond": [{"$ne": ["$lines.amount", None]}, 1, 0]
                    }
                },
                "line_tax": {"$sum": "$lines.tax_amt"},
                "tax_nonnull": {
                    "$sum": {
                        "$cond": [{"$ne": ["$lines.tax_amt", None]}, 1, 0]
                    }
                },
                "invoices": {"$addToSet": "$_id"},
            }
        },
    ]
    for item in db.invoices.aggregate(pipeline):
        key = (
            status_desc(codes, item["_id"]["s"]),
            line_type(item["_id"]["t"]),
        )
        existing = grouped.setdefault(
            key,
            {
                "count": 0,
                "amount": Decimal(0),
                "amount_nonnull": 0,
                "tax": Decimal(0),
                "tax_nonnull": 0,
                "invoices": set(),
            },
        )
        existing["count"] += item["line_count"]
        existing["amount_nonnull"] += item["amount_nonnull"]
        existing["tax_nonnull"] += item["tax_nonnull"]
        if item["amount_nonnull"]:
            amount = item["line_amount"]
            if isinstance(amount, Decimal128):
                amount = amount.to_decimal()
            existing["amount"] += amount
        if item["tax_nonnull"]:
            tax = item["line_tax"]
            if isinstance(tax, Decimal128):
                tax = tax.to_decimal()
            existing["tax"] += tax
        existing["invoices"].update(item["invoices"])
    return [
        (
            status,
            line,
            values["count"],
            _amount_total(values["amount"], values["amount_nonnull"]),
            _amount_total(values["tax"], values["tax_nonnull"]),
            len(values["invoices"]),
        )
        for (status, line), values in sorted(grouped.items())
    ]


def mongo_report_rows(batch_no):
    db = mongo_db()
    return status_rows_mongo(db, batch_no), line_rows_mongo(db, batch_no)


@reports.get("/api/reports/month-end")
def month_end():
    ns = request.args.get("ns", "demo")
    batch_no = ns_batch_no(ns)
    try:
        status_rows, line_rows = mongo_report_rows(batch_no)
    except Exception:  # estate offline: fail closed, never fabricate numbers
        logger.exception("month-end report failed for ns=%s", ns)
        return jsonify(ESTATE_UNAVAILABLE), 503
    body = report_meta(ns, source=MONGO_SOURCE)
    body["report"] = "month-end-finance"
    body["by_status"] = shape_status_rows(status_rows)
    body["by_status_line_type"] = shape_line_rows(line_rows)
    return jsonify(body)


@reports.get("/api/reports/reconciliation")
def reconciliation():
    ns = request.args.get("ns", "demo")
    batch_no = ns_batch_no(ns)
    try:
        balance_rows = oracle_query(BALANCES_SQL, {"batch_no": batch_no})
    except Exception:
        logger.exception("reconciliation report failed for ns=%s", ns)
        return jsonify(ESTATE_UNAVAILABLE), 503
    body = report_meta(ns, source=SOURCE)
    body["balances"] = shape_balances(balance_rows[0])
    # The legacy estate IS the source of truth: there is nothing to reconcile
    # against, so it reports baseline with no checks. Post-migration backends
    # return status pass|fail with per-check results instead.
    body["status"] = "baseline"
    body["checks"] = []
    return jsonify(body)
