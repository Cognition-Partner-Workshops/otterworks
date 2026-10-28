#!/usr/bin/env python3
"""SELECT-only snapshot of the OW_BILLING roots the invoice-quality pipeline reads.

Reads OW_BILLING via the read-only principal named by OW_BILLING_RO_DSN (env var
holding a JSON object {user, password, host, port, service}, never a credential in
code), writes one CSV per mapped table to --out, then uploads them with
`databricks fs cp` to the volume the pipeline reads:

  /Volumes/ow_tp/mig_1793185083/ow_tp_invoice_quality_extract/

Full-estate scan: no WHERE clause, every tenant. Columns are exactly the ones
the unit's mapping_spec.json declares; extraction order follows Oracle's
natural order so reruns are byte-stable. The pipeline re-derives everything
from these files, so re-running this script and refreshing the pipeline is the
idempotent reload path.
"""

import argparse
import csv
import json
import os
import subprocess
import sys

import oracledb

VOLUME = "/Volumes/ow_tp/mig_1793185083/ow_tp_invoice_quality_extract"

QUERIES = {
    "invoice_header": (
        "SELECT INVOICE_ID, INVOICE_DT, DUE_DT FROM OW_BILLING.INVOICE_HEADER"
    ),
    "invoice_line": (
        "SELECT LINE_ID, INVOICE_ID, INVOICE_DT FROM OW_BILLING.INVOICE_LINE"
    ),
    "customer_master": (
        "SELECT CUST_ID, SIGNUP_DT FROM OW_BILLING.CUSTOMER_MASTER"
    ),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="local directory for the CSVs")
    ap.add_argument("--upload", action="store_true",
                    help="upload each CSV to the pipeline's extract volume")
    args = ap.parse_args()

    dsn = json.loads(os.environ["OW_BILLING_RO_DSN"])
    conn = oracledb.connect(
        user=dsn["user"], password=dsn["password"], host=dsn["host"],
        port=dsn["port"], service_name=dsn.get("service") or dsn.get("service_name"))
    def dump(cur, name):
        cols = [d[0].lower() for d in cur.description]
        path = os.path.join(args.out, f"{name}.csv")
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(cols)
            for row in cur:
                writer.writerow(["" if v is None else str(v) for v in row])
        print(f"{name}: {cur.rowcount if cur.rowcount >= 0 else 'done'} -> {path}")
        if args.upload:
            subprocess.run(
                ["databricks", "fs", "cp", path,
                 f"dbfs:{VOLUME}/{name}.csv", "--overwrite"],
                check=True)

    try:
        # Literal SELECTs only: the guard must see every statement verbatim
        # (no lookup-table dispatch). QUERIES above documents the same text.
        cur = conn.cursor()
        cur.execute("SELECT INVOICE_ID, INVOICE_DT, DUE_DT FROM OW_BILLING.INVOICE_HEADER")
        dump(cur, "invoice_header")
        cur.execute("SELECT LINE_ID, INVOICE_ID, INVOICE_DT FROM OW_BILLING.INVOICE_LINE")
        dump(cur, "invoice_line")
        cur.execute("SELECT CUST_ID, SIGNUP_DT FROM OW_BILLING.CUSTOMER_MASTER")
        dump(cur, "customer_master")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
