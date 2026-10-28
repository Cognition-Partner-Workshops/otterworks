#!/usr/bin/env python3
"""SELECT-only snapshot of the OW_BILLING rows unit u-plans maps to Lakebase.

Reads OW_BILLING via the read-only principal named by OW_BILLING_RO_DSN (env var
holding a JSON object {user, password, host, port, service}; never a credential
in code) and writes one CSV per mapped object to --out. Tenant One only for the
tenant-scoped objects (tenant_id '00000000-0000-0000-0000-000000000001');
plans and codes are unfiltered reference data. Column order is exactly the
target-column order the loader's COPY statements declare; extraction order is
the key order so reruns are byte-stable. Every query is an inline literal the
guard can read. The loader drops and recreates the target tables, so re-running
extract + load is the idempotent reload path.
"""

import argparse
import csv
import json
import os
import sys

import oracledb

COLUMNS = {
    "plans": ["id", "code", "tier_cd", "monthly_fee", "included_units",
              "overage_rate", "active_yn"],
    "codes": ["code_type", "code_val", "code_desc"],
    "tenants": ["id", "name", "tax_exempt_yn", "status_cd"],
    "subscriptions": ["id", "tenant_id", "plan_id", "starts_on", "ends_on",
                      "status_cd", "suspended_on"],
    "subscriptions_hist": ["hist_id", "hist_dt", "hist_dt_raw", "hist_op", "id",
                           "tenant_id", "plan_id", "starts_on", "ends_on",
                           "status_cd", "suspended_on"],
}


def _cell(v):
    if v is None:
        return ""
    return str(v)


def _dump(cur, name, path):
    cols = COLUMNS[name]
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(cols)
        rows = 0
        for row in cur:
            writer.writerow([_cell(v) for v in row])
            rows += 1
    print(f"{name}: {rows} rows -> {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="local directory for the CSVs")
    args = ap.parse_args()

    dsn = json.loads(os.environ["OW_BILLING_RO_DSN"])
    conn = oracledb.connect(
        user=dsn["user"], password=dsn["password"], host=dsn["host"],
        port=dsn["port"], service_name=dsn.get("service") or dsn.get("service_name"))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT ID, CODE, TIER_CD, MONTHLY_FEE, INCLUDED_UNITS, "
            "OVERAGE_RATE, ACTIVE_YN FROM OW_BILLING.PLANS ORDER BY ID")
        _dump(cur, "plans", os.path.join(args.out, "plans.csv"))
        cur.execute(
            "SELECT CODE_TYPE, CODE_VAL, CODE_DESC FROM OW_BILLING.CODES "
            "ORDER BY CODE_TYPE, CODE_VAL")
        _dump(cur, "codes", os.path.join(args.out, "codes.csv"))
        cur.execute(
            "SELECT ID, NAME, TAX_EXEMPT_YN, STATUS_CD FROM OW_BILLING.TENANTS "
            "WHERE ID = '00000000-0000-0000-0000-000000000001' ORDER BY ID")
        _dump(cur, "tenants", os.path.join(args.out, "tenants.csv"))
        cur.execute(
            "SELECT ID, TENANT_ID, PLAN_ID, STARTS_ON, ENDS_ON, STATUS_CD, "
            "SUSPENDED_ON FROM OW_BILLING.SUBSCRIPTIONS "
            "WHERE TENANT_ID = '00000000-0000-0000-0000-000000000001' "
            "ORDER BY ID")
        _dump(cur, "subscriptions", os.path.join(args.out, "subscriptions.csv"))
        # HIST_DT is read twice: once for hist_dt (the canonicalised column) and
        # once for hist_dt_raw (the verbatim string), matching the spec's dual
        # mapping.
        cur.execute(
            "SELECT HIST_ID, HIST_DT, HIST_DT, HIST_OP, ID, TENANT_ID, "
            "PLAN_ID, STARTS_ON, ENDS_ON, STATUS_CD, SUSPENDED_ON "
            "FROM OW_BILLING.SUBSCRIPTIONS_HIST "
            "WHERE TENANT_ID = '00000000-0000-0000-0000-000000000001' "
            "ORDER BY HIST_ID")
        _dump(cur, "subscriptions_hist",
              os.path.join(args.out, "subscriptions_hist.csv"))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
