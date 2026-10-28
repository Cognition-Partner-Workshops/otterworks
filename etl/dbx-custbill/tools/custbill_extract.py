#!/usr/bin/env python3
"""Converted Oracle month-end CUSTBILL extract (custbill-feed unit).

Port of etl/legacy-extra/tools/oracle_custbill_extract.py: same EXTRACT_SQL
(invoice_header join customer_master left join tenants, batch_no/admin-tenant
filter), same 65-char CBCUST01 record serialization. Two artifacts:

- `CUSTBILL_<NS>_ORACLE.dat`   byte-compatible with the legacy drop
- `CUSTBILL_<NS>_ORACLE.feed`  keyed JSONL snapshot ({"invoice_id", "record"})
  the staging landing consumes — invoice_id is the lineage key the flat
  record cannot carry.

Runs wherever the read-only source is reachable; the DSN comes from the
OW_BILLING_RO_DSN secret (JSON {user,password,dsn} or oracle:// URI form).
"""

import argparse
import hashlib
import json
import os
import unicodedata
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import oracledb

ADMIN_TENANT_ID = "a0000000-0000-0000-0000-000000000001"
EXTRACT_SQL = """
SELECT h.invoice_id,
       c.cust_no,
       c.cust_name,
       TO_DATE(h.invoice_dt, 'DD-MON-RR') AS period_end,
       h.total_amt,
       CASE WHEN h.total_amt < 0 THEN '02' ELSE '01' END AS record_type
  FROM ow_billing.invoice_header h
  JOIN ow_billing.customer_master c ON c.cust_id = h.cust_id
  LEFT JOIN ow_billing.tenants t ON t.id = h.tenant_id
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


def _ascii_text(value):
    return (
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "replace")
        .decode()
    )


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


def _row_mapping(row):
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


def _connect(secret_name="OW_BILLING_RO_DSN"):
    raw = os.environ[secret_name].strip()
    if raw.startswith("{"):
        d = json.loads(raw)
        return oracledb.connect(
            user=d["user"], password=d["password"],
            host=d["host"], port=int(d["port"]), service_name=d["service"],
        )
    if "://" in raw:  # oracle://user:pass@host:port/service
        return oracledb.connect(dsn=raw)
    userpass, _, dsn = raw.partition("@")
    user, _, password = userpass.partition("/")
    return oracledb.connect(user=user, password=password, dsn=dsn)


def extract(ns, out_dir, connection=None):
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    basename = f"CUSTBILL_{ns.upper()}_ORACLE"
    if connection is None:
        connection = _connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                EXTRACT_SQL,
                {"batch_no": ns_batch_no(ns), "admin_tenant_id": ADMIN_TENANT_ID},
            )
            rows = [_row_mapping(row) for row in cursor.fetchall()]
    finally:
        if connection is not None:
            connection.close()

    rows = sort_rows(rows)
    dat_path = out_path / f"{basename}.dat"
    feed_path = out_path / f"{basename}.feed"
    dat_tmp = dat_path.with_name(f"{dat_path.name}.tmp")
    feed_tmp = feed_path.with_name(f"{feed_path.name}.tmp")
    with dat_tmp.open("w", encoding="ascii", newline="\n") as output:
        for row in rows:
            output.write(format_record(row))
            output.write("\n")
    os.replace(dat_tmp, dat_path)
    with feed_tmp.open("w", encoding="utf-8", newline="\n") as output:
        for row in rows:
            output.write(json.dumps(
                {"invoice_id": row["invoice_id"], "record": format_record(row)},
                separators=(",", ":"), ensure_ascii=True,
            ))
            output.write("\n")
    os.replace(feed_tmp, feed_path)
    return dat_path, feed_path, len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ns", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    dat_path, feed_path, count = extract(args.ns, args.out)
    print(f"wrote {dat_path} ({count} records)")
    print(f"wrote {feed_path} ({count} keyed rows)")


if __name__ == "__main__":
    main()
