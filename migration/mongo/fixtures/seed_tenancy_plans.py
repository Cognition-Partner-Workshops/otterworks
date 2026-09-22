#!/usr/bin/env python3
"""Synthetic TENANTS/PLANS/SUBSCRIPTIONS/SUBSCRIPTIONS_HIST rows for the
w1-b01 fixture (LOCAL ORACLE FIXTURE ONLY).

The fixture already carries the static rows from schema/03_seed_static.sql.
This seed adds synthetic rows exercising the census traps reachable on this
unit's tables:

- subscription lifecycle: open (ends_on NULL), closed, suspended, cancelled
  (status_cd = 30, the value trg_sub_no_uncancel pins), and status_cd values
  NOT in CODES (facade UNKNOWN(<cd>) path)
- SUBSCRIPTIONS_HIST rows with HIST_DT 'DD-MON-YY HH24:MI:SS' strings like
  trg_subscriptions_hist writes (01_tables.sql:218), INS/UPD/DEL ops, sparse
  NULL columns (null_missing_equiv). An unparseable hist_dt is NOT plantable
  in the baseline: the harness canonicalizer keeps raw strings it cannot
  convert, so such a row is a legitimate recon FAIL, not a quarantine case
- plans at NUMBER scale edges (monthly_fee 12,2 / overage_rate 12,6),
  tier_cd values not in CODES, active_yn 'N'
- tenants with tax_exempt_yn 'Y'/'N' and status_cd outside CODES

Idempotent: MERGE on each table's PK. Writes .migration/fixtures/w1-b01.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / ".migration" / "fixtures" / "w1-b01.json"

TENANTS = [
    # (id, name, tax_exempt_yn, status_cd)
    ("SYNTH-TEN-1", "Synth Tenant One", "Y", 10),
    ("SYNTH-TEN-2", "Synth Tenant Two", "N", 10),
    ("SYNTH-TEN-3", "Synth Tenant Three", "N", 999),   # status not in CODES
]

PLANS = [
    # (id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn)
    ("SYNTH-PLAN-A", "SYNTH-A", 1, "0.00", 0, "0.000000", "Y"),
    ("SYNTH-PLAN-B", "SYNTH-B", 999, "999999.99", 1000000, "1.234567", "Y"),
    ("SYNTH-PLAN-C", "SYNTH-C", 2, "49.95", 100, "0.050000", "N"),  # retired plan
]

SUBSCRIPTIONS = [
    # (id, tenant_id, plan_id, starts_on, ends_on, status_cd, suspended_on)
    ("SYNTH-SUB-OPEN", "SYNTH-TEN-1", "SYNTH-PLAN-A",
     dt.date(2026, 1, 1), None, 10, None),                       # open
    ("SYNTH-SUB-CLOSED", "SYNTH-TEN-1", "SYNTH-PLAN-B",
     dt.date(2025, 1, 1), dt.date(2025, 12, 31), 20, None),      # closed
    ("SYNTH-SUB-CXL", "SYNTH-TEN-2", "SYNTH-PLAN-A",
     dt.date(2024, 6, 1), dt.date(2024, 9, 1), 30, None),        # cancelled (pinned by trigger)
    ("SYNTH-SUB-SUSP", "SYNTH-TEN-2", "SYNTH-PLAN-B",
     dt.date(2026, 3, 1), None, 10, dt.date(2026, 7, 15)),       # suspended
    ("SYNTH-SUB-UNKNOWN", "SYNTH-TEN-3", "SYNTH-PLAN-B",
     dt.date(2026, 2, 2), None, 42, None),                       # status not in CODES
]

HIST = [
    # (hist_id, hist_dt, hist_op, id, tenant_id, plan_id, starts_on, ends_on,
    #  status_cd, suspended_on) -- hist_id high band, clear of the DDL sequence
    (900001, "01-JAN-26 00:00:01", "INS", "SYNTH-SUB-OPEN",
     "SYNTH-TEN-1", "SYNTH-PLAN-A", dt.date(2026, 1, 1), None, 10, None),
    (900002, "15-JUN-26 12:30:45", "UPD", "SYNTH-SUB-OPEN",
     "SYNTH-TEN-1", "SYNTH-PLAN-A", dt.date(2026, 1, 1), None, 10, None),
    (900003, "01-SEP-24 09:15:00", "UPD", "SYNTH-SUB-CXL",
     "SYNTH-TEN-2", "SYNTH-PLAN-A", dt.date(2024, 6, 1),
     dt.date(2024, 9, 1), 30, None),
    (900004, "15-JUL-26 23:59:59", "UPD", "SYNTH-SUB-SUSP",
     "SYNTH-TEN-2", "SYNTH-PLAN-B", dt.date(2026, 3, 1), None, 10,
     dt.date(2026, 7, 15)),
    (900005, "01-OCT-25 08:00:00", "DEL", "SYNTH-SUB-GONE",
     "SYNTH-TEN-3", "SYNTH-PLAN-C", dt.date(2025, 1, 1),
     dt.date(2025, 10, 1), 20, None),                  # hist for a deleted sub
    (900006, None, "INS", "SYNTH-SUB-NODATE",
     "SYNTH-TEN-1", "SYNTH-PLAN-A", None, None, None, None),  # all-sparse row
    (900008, "31-DEC-25 18:45:30", None, "SYNTH-SUB-CLOSED",
     "SYNTH-TEN-1", "SYNTH-PLAN-B", dt.date(2025, 1, 1),
     dt.date(2025, 12, 31), 20, None),                 # NULL hist_op
]

def connection(uri: str):
    """Declares the migration target for the offline run. MongoClient is lazy
    -- this opens no socket; the seeder only ever touches Oracle."""
    from pymongo import MongoClient
    return MongoClient(uri)


def _connect(dsn_override=None):
    import oracledb
    raw = os.environ.get("ORACLE_FIXTURE_DSN")
    if not raw:
        sys.exit("ORACLE_FIXTURE_DSN not set (JSON {user,password,dsn})")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _local import require_local_dsn
    dsn = json.loads(raw)
    easy = dsn_override or dsn["dsn"]
    require_local_dsn(easy)
    return oracledb.connect(user=dsn["user"], password=dsn["password"],
                            dsn=easy)





def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=None,
                    help="override the dsn field of ORACLE_FIXTURE_DSN "
                         "(spell the fixture host out, e.g. 127.0.0.1:1521/FREEPDB1)")
    args = ap.parse_args()
    connection(os.environ.get(
        "MONGO_LOCAL_URI", "mongodb://127.0.0.1:27017/ow_billing_offline"))
    conn = _connect(args.dsn)
    cur = conn.cursor()
    for r in TENANTS:
        cur.execute(
            """MERGE INTO tenants t
               USING (SELECT :1 id, :2 name, :3 tax_exempt_yn, :4 status_cd
                      FROM dual) s
               ON (t.id = s.id)
               WHEN MATCHED THEN UPDATE SET name = s.name,
                   tax_exempt_yn = s.tax_exempt_yn, status_cd = s.status_cd
               WHEN NOT MATCHED THEN INSERT VALUES (s.id, s.name,
                   s.tax_exempt_yn, s.status_cd)""",
            r,
        )
    for r in PLANS:
        cur.execute(
            """MERGE INTO plans t
               USING (SELECT :1 id, :2 code, :3 tier_cd, :4 monthly_fee,
                            :5 included_units, :6 overage_rate, :7 active_yn
                      FROM dual) s
               ON (t.id = s.id)
               WHEN MATCHED THEN UPDATE SET code = s.code, tier_cd = s.tier_cd,
                   monthly_fee = s.monthly_fee, included_units = s.included_units,
                   overage_rate = s.overage_rate, active_yn = s.active_yn
               WHEN NOT MATCHED THEN INSERT VALUES (s.id, s.code, s.tier_cd,
                   s.monthly_fee, s.included_units, s.overage_rate,
                   s.active_yn)""",
            r,
        )
    for r in SUBSCRIPTIONS:
        cur.execute(
            """MERGE INTO subscriptions t
               USING (SELECT :1 id, :2 tenant_id, :3 plan_id, :4 starts_on,
                            :5 ends_on, :6 status_cd, :7 suspended_on
                      FROM dual) s
               ON (t.id = s.id)
               WHEN MATCHED THEN UPDATE SET tenant_id = s.tenant_id,
                   plan_id = s.plan_id, starts_on = s.starts_on,
                   ends_on = s.ends_on, status_cd = s.status_cd,
                   suspended_on = s.suspended_on
               WHERE DECODE(t.tenant_id, s.tenant_id, 0, 1) = 1
                  OR DECODE(t.plan_id, s.plan_id, 0, 1) = 1
                  OR DECODE(t.starts_on, s.starts_on, 0, 1) = 1
                  OR DECODE(t.ends_on, s.ends_on, 0, 1) = 1
                  OR DECODE(t.status_cd, s.status_cd, 0, 1) = 1
                  OR DECODE(t.suspended_on, s.suspended_on, 0, 1) = 1
               WHEN NOT MATCHED THEN INSERT VALUES (s.id, s.tenant_id,
                   s.plan_id, s.starts_on, s.ends_on, s.status_cd,
                   s.suspended_on)""",
            r,
        )
    for r in HIST:
        cur.execute(
            """MERGE INTO subscriptions_hist t
               USING (SELECT :1 hist_id, :2 hist_dt, :3 hist_op, :4 id,
                            :5 tenant_id, :6 plan_id, :7 starts_on, :8 ends_on,
                            :9 status_cd, :10 suspended_on FROM dual) s
               ON (t.hist_id = s.hist_id)
               WHEN MATCHED THEN UPDATE SET hist_dt = s.hist_dt,
                   hist_op = s.hist_op, id = s.id, tenant_id = s.tenant_id,
                   plan_id = s.plan_id, starts_on = s.starts_on,
                   ends_on = s.ends_on, status_cd = s.status_cd,
                   suspended_on = s.suspended_on
               WHEN NOT MATCHED THEN INSERT VALUES (s.hist_id, s.hist_dt,
                   s.hist_op, s.id, s.tenant_id, s.plan_id, s.starts_on,
                   s.ends_on, s.status_cd, s.suspended_on)""",
            r,
        )
    # Hygiene for the removed unparseable-date trap row (was in an earlier
    # fixture build; recon-unsafe, see module docstring).
    cur.execute("DELETE FROM subscriptions_hist WHERE hist_id = 900007")
    conn.commit()
    row_counts = {}
    cur.execute("SELECT COUNT(*) FROM tenants")
    row_counts["TENANTS"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM plans")
    row_counts["PLANS"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM subscriptions")
    row_counts["SUBSCRIPTIONS"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM subscriptions_hist")
    row_counts["SUBSCRIPTIONS_HIST"] = cur.fetchone()[0]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({
        "source": "oracle fixture FIXTURE@FREEPDB1 built from services/legacy-billing/db/oracle DDL",
        "method": "synthetic",
        "masked_columns": [],
        "produced_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "produced_by": "migration/mongo/fixtures/seed_tenancy_plans.py",
        "row_counts": row_counts,
    }, indent=2) + "\n")
    print(f"tenancy-plans: seeded {len(TENANTS)} tenants, {len(PLANS)} plans, "
          f"{len(SUBSCRIPTIONS)} subscriptions, {len(HIST)} hist rows "
          f"(table counts {row_counts})")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
