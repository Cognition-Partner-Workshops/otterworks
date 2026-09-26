#!/usr/bin/env python3
"""Loader for unit u-06-invoice-header-bulk.

Reads Oracle INVOICE_HEADER + INVOICE_LINE and writes MongoDB
``invoiceHeader`` documents with embedded ``lines[]`` (parent key
INVOICE_ID, element key LINE_ID -> lineId). Orphan lines and malformed
values are quarantined with reason codes, never dropped silently.

Usage:
    python3 load_invoice_header.py \
        --source-dsn-secret OW_BILLING_FIXTURE_DSN \
        --target-uri-secret MONGO_LOCAL_URI \
        --target-db ow_billing_migration \
        [--summary-out path/to/load.summary.json]

Both secrets are env-var NAMES: the source secret holds a JSON
{user, password, dsn}; the target secret holds a MongoDB URI.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

UNIT = "u-06-invoice-header-bulk"
COLLECTION = "invoiceHeader"
BATCH_SIZE = 1000
QUARANTINE_ECHO_LIMIT = 100

ALLOWED_TARGETS = (
    Path(__file__).resolve().parents[4] / ".migration" / "allowed_targets.json"
)

DATE_FORMAT = "%d-%b-%y"
YN_TRUE = {"Y", "T", "1", "TRUE", "YES"}
YN_FALSE = {"N", "F", "0", "FALSE", "NO"}


class Quarantine:
    def __init__(self):
        self.reasons = {}
        self.rows = []

    def add(self, reason, key):
        self.reasons[reason] = self.reasons.get(reason, 0) + 1
        if len(self.rows) < QUARANTINE_ECHO_LIMIT:
            self.rows.append({"reason": reason, **key})

    @property
    def total(self):
        return sum(self.reasons.values())


def _str(value):
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None


def _long(value):
    if value is None:
        return None
    from bson.int64 import Int64

    return Int64(int(value))


def _decimal(value):
    if value is None:
        return None
    from bson.decimal128 import Decimal128

    return Decimal128(str(value))


def _date(value, quarantine, column, key):
    if value is None or str(value) == "":
        return None
    try:
        return datetime.strptime(str(value), DATE_FORMAT)
    except ValueError:
        quarantine.add(f"bad_date:{column}", key)
        return None


def _yn(value, quarantine, key):
    if value is None:
        return None
    token = str(value).strip().upper()
    if token == "":
        return None
    if token in YN_TRUE:
        return True
    if token in YN_FALSE:
        return False
    quarantine.add("bad_yn:POSTED_YN", key)
    return None


def _csv(value):
    if value is None or str(value) == "":
        return None
    parts = [part.strip() for part in str(value).split(",") if part.strip()]
    return parts or None


def _set(doc, field, value):
    if value is not None:
        doc[field] = value


def header_doc(row, quarantine):
    """Build one invoiceHeader document from an INVOICE_HEADER row tuple."""
    (
        invoice_id,
        invoice_no,
        cust_id,
        tenant_id,
        invoice_dt,
        due_dt,
        status_cd,
        total_amt,
        batch_no,
    ) = row
    key = {"invoice_id": invoice_id}
    doc = {"_id": invoice_id}
    _set(doc, "invoiceNo", _str(invoice_no))
    _set(doc, "custId", _str(cust_id))
    _set(doc, "tenantId", _str(tenant_id))
    _set(doc, "invoiceDt", _date(invoice_dt, quarantine, "INVOICE_DT", key))
    _set(doc, "dueDt", _date(due_dt, quarantine, "DUE_DT", key))
    _set(doc, "statusCd", _long(status_cd))
    _set(doc, "totalAmt", _decimal(total_amt))
    _set(doc, "batchNo", _long(batch_no))
    doc["lines"] = []
    return doc


def line_elem(row, quarantine):
    """Build one lines[] element from an INVOICE_LINE row tuple.

    INVOICE_ID is not stored inside the element (it is the parent _id).
    """
    (
        line_id,
        _invoice_id,
        invoice_no,
        cust_id,
        cust_no,
        cust_name,
        tenant_id,
        line_no,
        line_type_cd,
        item_desc,
        qty,
        unit_price,
        amount,
        tax_amt,
        invoice_dt,
        service_period,
        posted_yn,
        gl_acct_csv,
        batch_no,
        src_system,
    ) = row
    key = {"line_id": line_id}
    elem = {"lineId": line_id}
    _set(elem, "invoiceNo", _str(invoice_no))
    _set(elem, "custId", _str(cust_id))
    _set(elem, "custNo", _str(cust_no))
    _set(elem, "custName", _str(cust_name))
    _set(elem, "tenantId", _str(tenant_id))
    _set(elem, "lineNo", _long(line_no))
    _set(elem, "lineTypeCd", _long(line_type_cd))
    _set(elem, "itemDesc", _str(item_desc))
    _set(elem, "qty", _decimal(qty))
    _set(elem, "unitPrice", _decimal(unit_price))
    _set(elem, "amount", _decimal(amount))
    _set(elem, "taxAmt", _decimal(tax_amt))
    _set(elem, "invoiceDt", _date(invoice_dt, quarantine, "INVOICE_DT", key))
    _set(elem, "servicePeriod", _str(service_period))
    _set(elem, "posted", _yn(posted_yn, quarantine, key))
    _set(elem, "glAcct", _csv(gl_acct_csv))
    _set(elem, "batchNo", _long(batch_no))
    _set(elem, "srcSystem", _str(src_system))
    return elem


def _line_sort_key(elem):
    line_no = elem.get("lineNo")
    # missing lineNo sorts first, then (lineNo, lineId)
    return (1 if line_no is not None else 0, line_no if line_no is not None else 0, elem["lineId"])


def assemble(header_rows, line_rows):
    """Pair INVOICE_HEADER and INVOICE_LINE rows into documents.

    Returns (docs, quarantine). Deterministic: headers keyed by _id in
    invoice_id order, each lines[] sorted by (lineNo, lineId) with missing
    lineNo first. Orphans, duplicates, and malformed values are quarantined.
    """
    quarantine = Quarantine()
    docs = {}
    for row in header_rows:
        invoice_id = row[0]
        if invoice_id in docs:
            quarantine.add("duplicate_key", {"invoice_id": invoice_id})
            continue
        docs[invoice_id] = header_doc(row, quarantine)
    seen_lines = set()
    embedded = 0
    for row in line_rows:
        line_id, invoice_id = row[0], row[1]
        if line_id in seen_lines:
            quarantine.add("duplicate_key", {"line_id": line_id})
            continue
        seen_lines.add(line_id)
        parent = docs.get(invoice_id)
        if parent is None:
            quarantine.add("orphan_line", {"line_id": line_id, "invoice_id": invoice_id})
            continue
        parent["lines"].append(line_elem(row, quarantine))
        embedded += 1
    for doc in docs.values():
        doc["lines"].sort(key=_line_sort_key)
    return list(docs.values()), quarantine, embedded


def _check_allowlist(target_db):
    allowlist = json.loads(ALLOWED_TARGETS.read_text())
    if target_db not in allowlist.get("databases", []):
        raise SystemExit(
            f"target database {target_db!r} is not in {ALLOWED_TARGETS} "
            f"databases {allowlist.get('databases')}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn-secret", required=True)
    parser.add_argument("--target-uri-secret", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--summary-out")
    args = parser.parse_args()

    _check_allowlist(args.target_db)

    source_raw = os.getenv(args.source_dsn_secret)
    target_uri = os.getenv(args.target_uri_secret)
    if not source_raw or not target_uri:
        raise SystemExit(
            "missing env vars: "
            f"{args.source_dsn_secret} / {args.target_uri_secret}"
        )
    source = json.loads(source_raw)

    import oracledb
    from pymongo import MongoClient

    oracledb.defaults.fetch_decimals = True

    started = time.time()
    connection = oracledb.connect(
        user=source["user"], password=source["password"], dsn=source["dsn"]
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT invoice_id, invoice_no, cust_id, tenant_id, invoice_dt, due_dt, status_cd, total_amt, batch_no FROM invoice_header ORDER BY invoice_id")
            header_rows = cursor.fetchall()
            cursor.execute("SELECT line_id, invoice_id, invoice_no, cust_id, cust_no, cust_name, tenant_id, line_no, line_type_cd, item_desc, qty, unit_price, amount, tax_amt, invoice_dt, service_period, posted_yn, gl_acct_csv, batch_no, src_system FROM invoice_line ORDER BY invoice_id, line_no, line_id")
            line_rows = cursor.fetchall()
    finally:
        connection.close()

    docs, quarantine, embedded = assemble(header_rows, line_rows)

    client = MongoClient(target_uri)
    try:
        db = client[args.target_db]
        db.drop_collection(COLLECTION)
        collection = db[COLLECTION]
        for offset in range(0, len(docs), BATCH_SIZE):
            collection.insert_many(docs[offset : offset + BATCH_SIZE], ordered=False)
        indexes = ["batchNo", "tenantId", "lines.lineId"]
        for field in indexes:
            collection.create_index(field)
    finally:
        client.close()

    summary = {
        "unit": UNIT,
        "source": "invoice_header + invoice_line (Oracle)",
        "target": f"{args.target_db}.{COLLECTION}",
        "loaded_headers": len(docs),
        "embedded_lines": embedded,
        "quarantined": quarantine.total,
        "quarantine_reasons": quarantine.reasons,
        "quarantine_rows": quarantine.rows,
        "indexes": indexes,
        "elapsed_s": round(time.time() - started, 3),
    }
    text = json.dumps(summary, indent=2, default=str)
    print(text)
    if args.summary_out:
        Path(args.summary_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_out).write_text(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
