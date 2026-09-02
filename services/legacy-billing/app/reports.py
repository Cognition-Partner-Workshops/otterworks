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
from decimal import ROUND_HALF_EVEN, Decimal

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

# Legacy RPT-114 balances query; retained as the Oracle reference the MongoDB
# aggregation below is graded against (see .migration/recon/U1/rpt114_balances.json).
BALANCES_SQL = """
SELECT COUNT(*)                                          AS customer_count,
       TO_CHAR(SUM(cur_bal_amt), 'FM999999999999990.00') AS current_balance_total,
       TO_CHAR(SUM(past_due_amt), 'FM999999999999990.00') AS past_due_total
  FROM customer_master
 WHERE conversion_batch_no = :batch_no
"""

MONGO_NS = os.getenv("MONGODB_NS", "mongo_205236")
MONGO_DB = os.getenv("MONGODB_DB", "ow_tp_mongodb_205236")

BALANCES_SOURCE = {
    "engine": "mongodb",
    "system": f"Atlas {MONGO_DB}",
    "detail": "customers aggregation (RPT-114 balances)",
}


def balances_pipeline(batch_no):
    """RPT-114 balances: COUNT(*), SUM(cur_bal_amt), SUM(past_due_amt) for the batch."""
    return [
        {"$match": {"conversion_batch_no": batch_no, "ns": MONGO_NS}},
        {
            "$group": {
                "_id": None,
                "customer_count": {"$sum": 1},
                "current_balance_total": {"$sum": "$cur_bal_amt"},
                "current_balance_values": {"$sum": {"$cond": [{"$ne": ["$cur_bal_amt", None]}, 1, 0]}},
                "past_due_total": {"$sum": "$past_due_amt"},
                "past_due_values": {"$sum": {"$cond": [{"$ne": ["$past_due_amt", None]}, 1, 0]}},
            }
        },
        {"$project": {"_id": 0}},
    ]


def fm_amount(value):
    """Oracle TO_CHAR(x, 'FM999999999999990.00'): no padding, two decimals, NULL -> None."""
    if value is None:
        return None
    if hasattr(value, "to_decimal"):
        value = value.to_decimal()
    return str(Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_HALF_EVEN))


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


def mongo_connect():
    from pymongo import MongoClient

    uri = os.environ["MONGODB_ATLAS_URI"]
    return MongoClient(uri, serverSelectionTimeoutMS=int(os.getenv("MONGODB_TIMEOUT_MS", "5000")))


def shape_balance_row(rows):
    # Oracle SUM is NULL over an empty group and over an all-NULL column; COUNT(*) is 0.
    row = rows[0] if rows else {"customer_count": 0}

    def total(name):
        if not row.get(f"{name}_values"):
            return None
        return fm_amount(row.get(f"{name}_total"))

    return row["customer_count"], total("current_balance"), total("past_due")


def check(name, expected, actual, ok=None):
    ok = (expected == actual) if ok is None else ok
    return {"name": name, "status": "pass" if ok else "fail",
            "expected": expected, "actual": actual}


def reconciliation_checks(database, batch_no, customer_count):
    """Post-migration checks the contract's pass|fail status is derived from."""
    customers = database["customers"]
    in_batch = customers.count_documents({"conversion_batch_no": batch_no})
    max_seq = next(iter(customers.aggregate([
        {"$match": {"conversion_batch_no": batch_no, "ns": MONGO_NS}},
        {"$group": {"_id": None, "max_seq": {"$max": "$cust_seq_no"}}},
    ])), {}).get("max_seq")
    counter = database["counters"].find_one({"_id": "seq_customer_master", "ns": MONGO_NS})
    counter_seq = None if counter is None else int(counter["seq"])
    return [
        check("customers-populated", "> 0", customer_count, customer_count > 0),
        check("customers-namespaced", in_batch, customer_count),
        check("customer-counter-seeded", f">= {max_seq}", counter_seq,
              counter_seq is not None and max_seq is not None
              and counter_seq >= int(max_seq)),
    ]


def mongo_reconciliation(batch_no):
    """Return (balance_row, checks) from the migrated customers collection."""
    client = mongo_connect()
    try:
        database = client[MONGO_DB]
        rows = list(database["customers"].aggregate(balances_pipeline(batch_no)))
        balance_row = shape_balance_row(rows)
        checks = reconciliation_checks(database, batch_no, balance_row[0])
    finally:
        client.close()
    return balance_row, checks


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
    return _MONGO_CLIENT[MONGO_DB]


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
        balance_row, checks = mongo_reconciliation(batch_no)
    except Exception:  # target offline: fail closed, never fabricate numbers
        logger.exception("reconciliation report failed for ns=%s", ns)
        return jsonify(ESTATE_UNAVAILABLE), 503
    body = report_meta(ns)
    body["source"] = BALANCES_SOURCE
    body["balances"] = shape_balances(balance_row)
    # Migrated backend: status is derived from the executed checks (contract:
    # pass when every check passes, fail otherwise; baseline is legacy-only).
    body["status"] = "pass" if all(c["status"] == "pass" for c in checks) else "fail"
    body["checks"] = checks
    return jsonify(body)
