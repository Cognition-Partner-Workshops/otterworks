#!/usr/bin/env python3
"""Run 20260927b, unit lakebase_scaffold: load the four reference tables into Lakebase.

Reads the JSON lines produced by extract_reference.py on stdin and COPYs them (psycopg 3,
COPY ... FROM STDIN) into ow_tp.billing.{codes,plans,tenants,usage_events} on Lakebase branch
mig-20260927b-w0 (literal host; the password comes from ~/.pgpass written from the
generate-database-credential token, never from the command line). Run apply.sh first: it
drop/recreates the four tables, so the load is a plain COPY into empty tables and touches
nothing else. Parents come before children in the stream (tenants before usage_events).
"""
import json
import sys

import psycopg

HOST = "ep-calm-sea-d1avwe82.database.us-west-2.cloud.databricks.com"
USER = "d9d1c4ec-29da-4ec7-9aa0-e932710d61e2"
DBNAME = "ow_tp"
COPY_SQL = {
    "codes": "COPY billing.codes (code_type, code_val, code_desc) FROM STDIN",
    "plans": "COPY billing.plans (id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn) FROM STDIN",
    "tenants": "COPY billing.tenants (id, name, tax_exempt_yn, status_cd) FROM STDIN",
    "usage_events": "COPY billing.usage_events (id, tenant_id, occurred_at, units, kind_cd) FROM STDIN",
}


def _copy_table(cur, table, rows):
    n = 0
    with cur.copy(COPY_SQL[table]) as cp:
        for r in rows:
            cp.write_row(r)
            n += 1
    return n


def main(argv):
    counts = {}
    pending_table, pending_rows = None, []
    with psycopg.connect(host=HOST, port=5432, dbname=DBNAME, user=USER, sslmode="require") as pg:
        with pg.cursor() as cur:
            for line in sys.stdin:
                rec = json.loads(line)
                if rec["t"] != pending_table:
                    if pending_table is not None:
                        counts[pending_table] = _copy_table(cur, pending_table, pending_rows)
                    if rec["t"] in counts:
                        raise SystemExit("table " + rec["t"] + " appears twice in the stream")
                    pending_table, pending_rows = rec["t"], []
                pending_rows.append(rec["r"])
            if pending_table is not None:
                counts[pending_table] = _copy_table(cur, pending_table, pending_rows)
        pg.commit()
    print(json.dumps({"unit": "lakebase_scaffold",
                      "loaded_rows": {"ow_tp.billing." + t: n for t, n in counts.items()}}, indent=2))
    return 0 if set(counts) == set(COPY_SQL) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
