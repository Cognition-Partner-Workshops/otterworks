#!/usr/bin/env python3
"""Extract invoice headers into the legacy CUSTBILL feed layout.

The source is the Oracle estate (INVOICE_HEADER joined to CUSTOMER_MASTER), or with
BILLING_BACKEND=mongo the migrated `invoice_feed` and `customers` collections in the
migration database on MONGODB_ATLAS_URI. Both produce the same sorted, byte-identical
65-byte CUSTBILL_<NS>_ORACLE.dat records.
"""

import argparse
import hashlib
import os
import unicodedata
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import oracledb

try:
    from pymongo import MongoClient
except ImportError:  # the Oracle-only batch host has no pymongo
    MongoClient = None

ADMIN_TENANT_ID = "a0000000-0000-0000-0000-000000000001"
MONGO_DATABASE = "ow_tp_billing_20261001T233613Z"
MONGO_URI_ENV = "MONGODB_ATLAS_URI"
MONGO_DATABASE_ENV = "MONGODB_DATABASE"
MONGO_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
MONGO_EXTRACT_PIPELINE = [
    {"$match": {"$or": [{"batchNo": None}, {"tenantId": ADMIN_TENANT_ID}]}},
    {"$lookup": {"from": "customers", "localField": "custId", "foreignField": "_id", "as": "customer"}},
    {"$unwind": "$customer"},
    {
        "$project": {
            "_id": 0,
            "invoice_id": "$_id",
            "cust_no": "$customer.custNo",
            "cust_name": "$customer.custName",
            "period_end": "$invoiceDate",
            "total_amt": "$totalAmt",
        }
    },
]
EXTRACT_SQL = """
SELECT h.invoice_id,
       c.cust_no,
       c.cust_name,
       TO_DATE(h.invoice_dt, 'DD-MON-RR') AS period_end,
       h.total_amt,
       CASE WHEN h.total_amt < 0 THEN '02' ELSE '01' END AS record_type
  FROM invoice_header h
  JOIN customer_master c ON c.cust_id = h.cust_id
  LEFT JOIN tenants t ON t.id = h.tenant_id
 WHERE h.batch_no = :batch_no
    OR h.tenant_id = :admin_tenant_id
 ORDER BY period_end, c.cust_no, h.invoice_id
"""


def ns_batch_no(ns):
    seed = int(hashlib.sha256(ns.encode()).hexdigest()[:8], 16)
    return seed % 90_000_000 + 1_000_000


def _period_text(value):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return datetime.strptime(str(value), "%Y-%m-%d").strftime("%Y%m%d")


def _amount_cents(value):
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))


def format_record(row):
    cust_no = _ascii_text(row["cust_no"])[:10].ljust(10)
    name = _ascii_text(row["cust_name"])[:30].ljust(30)
    period_end = _period_text(row["period_end"])
    cents = _amount_cents(row["total_amt"])
    if abs(cents) > 999_999_999_999:
        raise ValueError(
            f"invoice {row['invoice_id']} total exceeds CUSTBILL amount field"
        )
    record_type = "02" if cents < 0 else str(row.get("record_type") or "01")[:2].rjust(2, "0")
    record = f"{cust_no}{name}{period_end}{abs(cents):012d}USD{record_type}"
    assert len(record) == 65
    return record


def _ascii_text(value):
    return (
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "replace")
        .decode()
    )


def _row_mapping(row):
    if isinstance(row, dict):
        return row
    return {
        "invoice_id": row[0],
        "cust_no": row[1],
        "cust_name": row[2],
        "period_end": row[3],
        "total_amt": row[4],
        "record_type": row[5],
    }


def sort_rows(rows):
    return sorted(rows, key=lambda row: (
        _period_text(row["period_end"]),
        str(row["cust_no"] or ""),
        str(row["invoice_id"] or ""),
    ))


def mongo_mode():
    return os.getenv("BILLING_BACKEND", "").lower() == "mongo"


def mongo_pipeline(ns):
    pipeline = [dict(stage) for stage in MONGO_EXTRACT_PIPELINE]
    pipeline[0] = {"$match": {"$or": [{"batchNo": ns_batch_no(ns)}, {"tenantId": ADMIN_TENANT_ID}]}}
    return pipeline


def mongo_database(client):
    """Always the migration database; an override is honoured only on a loopback fixture."""
    override = os.getenv(MONGO_DATABASE_ENV)
    if not override or override == MONGO_DATABASE:
        return client[MONGO_DATABASE]
    if not all(host in MONGO_LOCAL_HOSTS for host, _port in client.nodes):
        raise RuntimeError(f"{MONGO_DATABASE_ENV} may only override the database on a local fixture")
    return client[override]


def extract_rows_oracle(ns, connection=None):
    if connection is None:
        connection = oracledb.connect(
            user=os.getenv("ORACLE_USER", "ow_billing"),
            password=os.getenv("ORACLE_PASSWORD", "ow_billing"),
            host=os.getenv("ORACLE_HOST", "localhost"),
            port=int(os.getenv("ORACLE_PORT", "52521")),
            service_name=os.getenv("ORACLE_SERVICE", "FREEPDB1"),
        )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                EXTRACT_SQL,
                {"batch_no": ns_batch_no(ns), "admin_tenant_id": ADMIN_TENANT_ID},
            )
            return [_row_mapping(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def extract_rows_mongo(ns, database=None):
    if database is None:
        if MongoClient is None:
            raise RuntimeError("BILLING_BACKEND=mongo needs pymongo")
        uri = os.getenv(MONGO_URI_ENV)
        if not uri:
            raise RuntimeError(f"{MONGO_URI_ENV} is not set")
        database = mongo_database(MongoClient(uri, tz_aware=True, appname="ow-custbill-extract"))
    return [_row_mapping(row) for row in database.invoice_feed.aggregate(mongo_pipeline(ns))]


def extract(ns, out_dir, connection=None, database=None):
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filename = f"CUSTBILL_{ns.upper()}_ORACLE.dat"
    if database is not None or (connection is None and mongo_mode()):
        rows = extract_rows_mongo(ns, database)
    else:
        rows = extract_rows_oracle(ns, connection)

    rows = sort_rows(rows)
    destination = out_path / filename
    temporary = destination.with_name(f"{destination.name}.tmp")
    with temporary.open("w", encoding="ascii", newline="\n") as output:
        for row in rows:
            output.write(format_record(row))
            output.write("\n")
    os.replace(temporary, destination)
    return destination, len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    destination, count = extract(args.ns, args.out)
    print(f"wrote {destination} ({count} records)")


if __name__ == "__main__":
    main()
