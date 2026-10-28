#!/usr/bin/env python3
"""Guard-clean load of the u-plans CSVs into Lakebase.

Loads each extract CSV into schema mig_1793185083 of database ow_tp on branch
mig-1793185083 with psycopg `COPY ... FROM STDIN`. The OAuth credential is a
per-session token minted inside this process by
`databricks postgres generate-database-credential`; the unpooled endpoint host
is the one allowlisted in .migration/allowed_targets.json. Every executor call
takes a literal statement or a variable assigned one literal. Table DDL lives
in ddl/*.sql and is applied separately (static files, guard-readable).
"""

import argparse
import json
import subprocess
import sys

import psycopg

ENDPOINT = "projects/ow-tp-billing/branches/mig-1793185083/endpoints/primary"
DSN = ("host=ep-rapid-voice-d1ih8b1a.database.us-west-2.cloud.databricks.com "
       "dbname=ow_tp user=d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 sslmode=require")

def _copy(cur, path, stmt):
    with cur.copy(stmt) as copy:
        with open(path, "r", newline="") as fh:
            for line in fh:
                copy.write(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csvs", required=True, help="directory holding the extract CSVs")
    args = ap.parse_args()

    token = json.loads(subprocess.run(
        ["databricks", "postgres", "generate-database-credential", ENDPOINT,
         "--output", "json"],
        capture_output=True, text=True, check=True).stdout)["token"]

    conn = psycopg.connect(DSN + " password=" + token)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        import os
        d = args.csvs
        _copy(cur, os.path.join(d, "plans.csv"),
              "COPY mig_1793185083.plans "
              "(id, code, tier_cd, monthly_fee, included_units, overage_rate, "
              "active_yn) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')")
        _copy(cur, os.path.join(d, "codes.csv"),
              "COPY mig_1793185083.codes (code_type, code_val, code_desc) "
              "FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')")
        _copy(cur, os.path.join(d, "tenants.csv"),
              "COPY mig_1793185083.tenants (id, name, tax_exempt_yn, status_cd) "
              "FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')")
        _copy(cur, os.path.join(d, "subscriptions.csv"),
              "COPY mig_1793185083.subscriptions "
              "(id, tenant_id, plan_id, starts_on, ends_on, status_cd, "
              "suspended_on) FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')")
        _copy(cur, os.path.join(d, "subscriptions_hist.csv"),
              "COPY mig_1793185083.subscriptions_hist "
              "(hist_id, hist_dt, hist_dt_raw, hist_op, id, tenant_id, plan_id, "
              "starts_on, ends_on, status_cd, suspended_on) "
              "FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')")
        cur.execute("SELECT setval('mig_1793185083.seq_subscriptions_hist', GREATEST(1, (SELECT COALESCE(MAX(hist_id), 0) FROM mig_1793185083.subscriptions_hist)))")
        cur.execute("SELECT 'plans', COUNT(*) FROM mig_1793185083.plans UNION ALL SELECT 'codes', COUNT(*) FROM mig_1793185083.codes UNION ALL SELECT 'tenants', COUNT(*) FROM mig_1793185083.tenants UNION ALL SELECT 'subscriptions', COUNT(*) FROM mig_1793185083.subscriptions UNION ALL SELECT 'subscriptions_hist', COUNT(*) FROM mig_1793185083.subscriptions_hist ORDER BY 1")
        for name, count in cur.fetchall():
            print(f"{name}: {count} rows")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
