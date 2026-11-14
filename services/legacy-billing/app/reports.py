"""Month-end finance reporting served straight from the OW_BILLING estate.

The estate is Oracle (BILLING_BACKEND=oracle) or its PostgreSQL takeout
(BILLING_BACKEND=ow_billing_pg). Both engines run the same rollup; on
Postgres the orphan lines sit in invoice_line_orphan and so are excluded the
same way the inner join excluded them on Oracle.

The report is the legacy RPT-114 rollup (see
db/oracle/ops/OPERATIONS_HANDBOOK.doc.txt and the CODES lookup conventions):
invoice counts and header totals by status, plus a line rollup by status and
line type. Orphaned INVOICE_LINE rows fall out of the join, exactly as finance
always ran it. Rows are namespace-scoped through the deterministic
conversion batch number.
"""

import hashlib
import logging
import csv
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from flask import Blueprint, jsonify, request

from backends import get_backend
from oracle_conn import oracle_connect as connect_oracle

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

PG_SOURCE = {
    "engine": "postgresql",
    "system": "OW_BILLING estate on PostgreSQL 15 (ow_tp_billing.ow_billing)",
    "detail": "invoice_header / invoice_line via codes lookup (RPT-114); "
              "orphan lines quarantined in invoice_line_orphan",
}

FINANCE_SOURCE = {
    "system": "CUSTBILL month-end batch",
    "detail": "ksh/Perl chain over Oracle CUSTBILL extract",
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

BALANCES_SQL = """
SELECT COUNT(*)                                          AS customer_count,
       TO_CHAR(SUM(cur_bal_amt), 'FM999999999999990.00') AS current_balance_total,
       TO_CHAR(SUM(past_due_amt), 'FM999999999999990.00') AS past_due_total
  FROM customer_master
 WHERE conversion_batch_no = :batch_no
"""

PG_MONEY = "'FM999999999999990.00'"
PG_STATUS = "COALESCE(st.code_desc, CONCAT('UNKNOWN(', h.status_cd, ')'))"
PG_LINE_TYPE = """CASE l.line_type_cd WHEN 1 THEN 'CHARGE'
                                WHEN 2 THEN 'CREDIT'
                                WHEN 3 THEN 'ADJUSTMENT'
                                WHEN 9 THEN 'MISC'
                                ELSE CONCAT('UNKNOWN(', l.line_type_cd, ')') END"""

# Counts are cast to numeric so they serialize exactly as Oracle NUMBER does.
PG_STATUS_SQL = f"""
SELECT {PG_STATUS} AS status_desc,
       COUNT(*)::numeric AS invoice_count,
       TO_CHAR(SUM(h.total_amt), {PG_MONEY}) AS header_total_amt
  FROM invoice_header h
  LEFT JOIN codes st ON st.code_type = 'INV_STATUS' AND st.code_val = h.status_cd
 WHERE h.batch_no = %(batch_no)s
 GROUP BY 1
 ORDER BY 1
"""

PG_LINE_SQL = f"""
SELECT {PG_STATUS} AS status_desc,
       {PG_LINE_TYPE} AS line_type,
       COUNT(*)::numeric AS line_count,
       TO_CHAR(SUM(l.amount), {PG_MONEY}) AS line_amount,
       TO_CHAR(SUM(l.tax_amt), {PG_MONEY}) AS line_tax,
       COUNT(DISTINCT h.invoice_id)::numeric AS invoices_touched
  FROM invoice_header h
  JOIN invoice_line l ON l.invoice_id = h.invoice_id
  LEFT JOIN codes st ON st.code_type = 'INV_STATUS' AND st.code_val = h.status_cd
 WHERE h.batch_no = %(batch_no)s
 GROUP BY 1, 2
 ORDER BY 1, 2
"""

PG_BALANCES_SQL = f"""
SELECT COUNT(*)::numeric AS customer_count,
       TO_CHAR(SUM(cur_bal_amt), {PG_MONEY}) AS current_balance_total,
       TO_CHAR(SUM(past_due_amt), {PG_MONEY}) AS past_due_total
  FROM customer_master
 WHERE conversion_batch_no = %(batch_no)s
"""

# Recomputed from the live Postgres tables on every call and compared with the
# Oracle-side figures migrate.py captured into migration_baseline.
PG_ACTUALS_SQL = f"""
WITH lines AS (
    SELECT amount, tax_amt FROM invoice_line WHERE batch_no = %(batch_no)s
    UNION ALL
    SELECT amount, tax_amt FROM invoice_line_orphan WHERE batch_no = %(batch_no)s
)
SELECT 'customers-count', COUNT(*)::text
  FROM customer_master WHERE conversion_batch_no = %(batch_no)s
UNION ALL
SELECT 'current-balance-total', TO_CHAR(SUM(cur_bal_amt), {PG_MONEY})
  FROM customer_master WHERE conversion_batch_no = %(batch_no)s
UNION ALL
SELECT 'past-due-total', TO_CHAR(SUM(past_due_amt), {PG_MONEY})
  FROM customer_master WHERE conversion_batch_no = %(batch_no)s
UNION ALL
SELECT 'customers-checksum',
       md5(string_agg(cust_id || ':' || TO_CHAR(cur_bal_amt, {PG_MONEY}) || E'\\n', ''
                      ORDER BY cust_id))
  FROM customer_master WHERE conversion_batch_no = %(batch_no)s
UNION ALL
SELECT 'invoice-headers-count', COUNT(*)::text
  FROM invoice_header WHERE batch_no = %(batch_no)s
UNION ALL
SELECT 'invoice-header-total', TO_CHAR(SUM(total_amt), {PG_MONEY})
  FROM invoice_header WHERE batch_no = %(batch_no)s
UNION ALL
SELECT 'invoice-lines-count', COUNT(*)::text FROM lines
UNION ALL
SELECT 'invoice-line-amount', TO_CHAR(SUM(amount), {PG_MONEY}) FROM lines
UNION ALL
SELECT 'invoice-line-tax', TO_CHAR(SUM(tax_amt), {PG_MONEY}) FROM lines
UNION ALL
SELECT 'orphan-lines-quarantined', COUNT(*)::text
  FROM invoice_line_orphan WHERE batch_no = %(batch_no)s
UNION ALL
SELECT 'orphan-line-amount', TO_CHAR(SUM(amount), {PG_MONEY})
  FROM invoice_line_orphan WHERE batch_no = %(batch_no)s
"""

PG_BASELINE_SQL = """
SELECT check_name, expected FROM migration_baseline WHERE batch_no = %(batch_no)s
"""

RECON_CHECKS = (
    "customers-count",
    "current-balance-total",
    "past-due-total",
    "customers-checksum",
    "invoice-headers-count",
    "invoice-header-total",
    "invoice-lines-count",
    "invoice-line-amount",
    "invoice-line-tax",
    "orphan-lines-quarantined",
    "orphan-line-amount",
)


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


ORACLE_QUERIES = {"status": STATUS_SQL, "line": LINE_SQL, "balances": BALANCES_SQL}
PG_QUERIES = {
    "status": PG_STATUS_SQL,
    "line": PG_LINE_SQL,
    "balances": PG_BALANCES_SQL,
    "actuals": PG_ACTUALS_SQL,
    "baseline": PG_BASELINE_SQL,
}


class FinanceReportTooLarge(Exception):
    pass


def oracle_query(sql, params):
    with connect_oracle() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def _on_postgres():
    return get_backend().NAME == "ow_billing_pg"


def estate_query(name, params):
    """Run report query `name` on whichever engine holds the estate."""
    if _on_postgres():
        return get_backend().report_query(PG_QUERIES[name], params)
    return oracle_query(ORACLE_QUERIES[name], params)


def reconciliation_checks(baseline_rows, actual_rows):
    expected = dict(baseline_rows)
    actual = dict(actual_rows)
    if not expected:
        return [{
            "name": "migration-baseline",
            "status": "fail",
            "expected": "recorded by migrate.py",
            "actual": "missing",
        }]
    return [
        {
            "name": name,
            "status": "pass" if expected.get(name) == actual.get(name) else "fail",
            "expected": expected.get(name),
            "actual": actual.get(name),
        }
        for name in RECON_CHECKS
    ]


def report_meta(ns):
    return {
        "namespace": ns,
        "batch_no": ns_batch_no(ns),
        "source": PG_SOURCE if _on_postgres() else SOURCE,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _admin_report_allowed():
    return "ADMIN" in {
        role.strip().upper()
        for role in request.headers.get("X-User-Roles", "").split(",")
        if role.strip()
    }


@reports.get("/api/reports/month-end")
def month_end():
    ns = request.args.get("ns", "demo")
    batch_no = ns_batch_no(ns)
    try:
        status_rows = estate_query("status", {"batch_no": batch_no})
        line_rows = estate_query("line", {"batch_no": batch_no})
    except Exception:  # estate offline: fail closed, never fabricate numbers
        logger.exception("month-end report failed for ns=%s", ns)
        return jsonify(ESTATE_UNAVAILABLE), 503
    body = report_meta(ns)
    body["report"] = "month-end-finance"
    body["by_status"] = shape_status_rows(status_rows)
    body["by_status_line_type"] = shape_line_rows(line_rows)
    return jsonify(body)


@reports.get("/api/v1/billing/admin/reports/month-end")
def admin_month_end():
    if not _admin_report_allowed():
        return jsonify(error="forbidden"), 403
    return month_end()


@reports.get("/api/reports/reconciliation")
def reconciliation():
    ns = request.args.get("ns", "demo")
    batch_no = ns_batch_no(ns)
    params = {"batch_no": batch_no}
    try:
        balance_rows = estate_query("balances", params)
        if _on_postgres():
            checks = reconciliation_checks(
                estate_query("baseline", params), estate_query("actuals", params),
            )
    except Exception:
        logger.exception("reconciliation report failed for ns=%s", ns)
        return jsonify(ESTATE_UNAVAILABLE), 503
    body = report_meta(ns)
    body["balances"] = shape_balances(balance_rows[0])
    if _on_postgres():
        body["status"] = "pass" if all(c["status"] == "pass" for c in checks) else "fail"
        body["checks"] = checks
    else:
        # The legacy estate IS the source of truth: there is nothing to
        # reconcile against, so it reports baseline with no checks.
        body["status"] = "baseline"
        body["checks"] = []
    return jsonify(body)


@reports.get("/api/v1/billing/admin/reports/reconciliation")
def admin_reconciliation():
    if not _admin_report_allowed():
        return jsonify(error="forbidden"), 403
    return reconciliation()


def finance_report_dir():
    configured = os.getenv("FINANCE_REPORT_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "etl/legacy-extra/reports"


def finance_report_path(ns):
    if not ns or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for char in ns):
        return None
    directory = finance_report_dir() / ns
    reports = sorted(
        directory.glob("finance_billing_*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return reports[0] if reports else None


def parse_finance_report(path):
    max_bytes = int(os.getenv("FINANCE_REPORT_MAX_BYTES", str(50 * 1024 * 1024)))
    if path.stat().st_size > max_bytes:
        raise FinanceReportTooLarge
    with path.open(newline="", encoding="utf-8") as stream:
        rows = []
        total_count = 0
        total_amount = Decimal("0.00")
        for row in csv.DictReader(stream):
            record_count = int(row["RecordCount"])
            total_count += record_count
            total_amount += Decimal(row["TotalAmount"])
            rows.append(
                {
                    "currency": row["Currency"],
                    "record_type": row["RecordType"],
                    "record_count": record_count,
                    "total_amount": row["TotalAmount"],
                }
            )
    return rows, {
        "record_count": total_count,
        "total_amount": f"{total_amount:.2f}",
    }


@reports.get("/api/reports/finance")
def finance():
    ns = request.args.get("ns", "demo")
    path = finance_report_path(ns)
    if path is None:
        return jsonify({
            "error": "no finance report for namespace",
            "detail": "run make tp-month-end NS=" + ns,
        }), 404
    try:
        rows, totals = parse_finance_report(path)
    except FinanceReportTooLarge:
        return jsonify(error="finance report too large"), 413
    generated_at = datetime.fromtimestamp(
        path.stat().st_mtime, timezone.utc,
    ).isoformat()
    return jsonify({
        "ns": ns,
        "source": {
            **FINANCE_SOURCE,
            "generated_at": generated_at,
            "file": path.name,
        },
        "rows": rows,
        "totals": totals,
    })


@reports.get("/api/v1/billing/admin/reports/finance")
def admin_finance():
    if not _admin_report_allowed():
        return jsonify(error="forbidden"), 403
    return finance()
