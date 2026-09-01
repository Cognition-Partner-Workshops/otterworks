"""Month-end finance reporting served straight from the Oracle billing estate.

The report is the legacy RPT-114 rollup (see
db/oracle/ops/OPERATIONS_HANDBOOK.doc.txt and the CODES lookup conventions):
invoice counts and header totals by status, plus a line rollup by status and
line type. Orphaned INVOICE_LINE rows fall out of the join, exactly as finance
always ran it. Rows are namespace-scoped through the deterministic
conversion batch number.
"""

import hashlib
import logging
import os
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal

from flask import Blueprint, jsonify, request

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

STATUS_SQL = """
SELECT NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')') AS status_desc,
       COUNT(*)                                   AS invoice_count,
       TO_CHAR(SUM(h.total_amt), 'FM999999999999990.00') AS header_total_amt
  FROM invoice_header h,
       codes st
 WHERE h.batch_no = :batch_no
   AND st.code_type (+) = 'INV_STATUS'
   AND st.code_val  (+) = h.status_cd
 GROUP BY NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')')
 ORDER BY 1
"""

LINE_SQL = """
SELECT NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')') AS status_desc,
       DECODE(l.line_type_cd, 1, 'CHARGE',
                              2, 'CREDIT',
                              3, 'ADJUSTMENT',
                              9, 'MISC',
                              'UNKNOWN(' || TO_CHAR(l.line_type_cd) || ')')
                                                  AS line_type,
       COUNT(*)                                   AS line_count,
       TO_CHAR(SUM(l.amount),  'FM999999999999990.00') AS line_amount,
       TO_CHAR(SUM(l.tax_amt), 'FM999999999999990.00') AS line_tax,
       COUNT(DISTINCT h.invoice_id)               AS invoices_touched
  FROM invoice_header h,
       invoice_line   l,
       codes          st
 WHERE h.batch_no = :batch_no
   AND h.invoice_id = l.invoice_id
   AND st.code_type (+) = 'INV_STATUS'
   AND st.code_val  (+) = h.status_cd
 GROUP BY NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')'),
          DECODE(l.line_type_cd, 1, 'CHARGE',
                                 2, 'CREDIT',
                                 3, 'ADJUSTMENT',
                                 9, 'MISC',
                                 'UNKNOWN(' || TO_CHAR(l.line_type_cd) || ')')
 ORDER BY 1, 2
"""

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
                "past_due_total": {"$sum": "$past_due_amt"},
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
    # SUM over an empty group is NULL in Oracle; COUNT(*) is 0.
    row = rows[0] if rows else {"customer_count": 0}
    return (
        row["customer_count"],
        fm_amount(row.get("current_balance_total")),
        fm_amount(row.get("past_due_total")),
    )


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


def report_meta(ns):
    return {
        "namespace": ns,
        "batch_no": ns_batch_no(ns),
        "source": SOURCE,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@reports.get("/api/reports/month-end")
def month_end():
    ns = request.args.get("ns", "demo")
    batch_no = ns_batch_no(ns)
    try:
        status_rows = oracle_query(STATUS_SQL, {"batch_no": batch_no})
        line_rows = oracle_query(LINE_SQL, {"batch_no": batch_no})
    except Exception:  # estate offline: fail closed, never fabricate numbers
        logger.exception("month-end report failed for ns=%s", ns)
        return jsonify(ESTATE_UNAVAILABLE), 503
    body = report_meta(ns)
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
