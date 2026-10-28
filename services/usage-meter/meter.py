"""OtterWorks usage meter: Delta on warehouse 565cd2fd713738c4, synced to Lakebase.

  snapshot  SELECT-only reads of Lakebase mig-invoicing-w1 / ow_tp_invoicing, written as
            CSV under build/snapshot/<table>/ for sql/00_load_snapshot.sql to load
  parity    row-for-row: Delta ow_tp.ow_tp_usage_meter.ow_tp_usage_meter vs the synced
            Lakebase table on mig-usage-meter (both SELECT-only)
  compare   one tenant's synced meter rows vs a read-only OW_BILLING query

Every statement is an inline literal at its call site so dbx_guard can read it.
"""
import argparse
import csv
import datetime
import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import oracledb
import psycopg

PROJECT = "ow-tp-billing"
SOURCE_BRANCH = "mig-invoicing-w1"
METER_BRANCH = "mig-usage-meter"
DATABASES = {SOURCE_BRANCH: "ow_tp", METER_BRANCH: "databricks_postgres"}
WAREHOUSE_ID = "565cd2fd713738c4"
SNAPSHOT_DIR = Path(__file__).parent / "build" / "snapshot"
METER_COLUMNS = ["tenant_id", "period_start", "period_end", "subscription_id", "plan_id", "plan_code",
                 "event_count", "used_units", "quota_units", "rollover_units", "billable_units",
                 "first_tier_units", "second_tier_units", "overage_amount"]
COLUMNS = ["period_start", "period_end", "plan", "events", "used", "quota", "rollover",
           "billable", "tier1", "tier2", "overage"]


def _cli_json(*args):
    return json.loads(subprocess.check_output(["databricks", *args, "-o", "json"]))


def lakebase_read_only(branch):
    endpoint = f"projects/{PROJECT}/branches/{branch}/endpoints/primary"
    host = _cli_json("postgres", "get-endpoint", endpoint)["status"]["hosts"]["host"]
    token = _cli_json("postgres", "generate-database-credential", endpoint)["token"]
    user = _cli_json("current-user", "me")["userName"]
    conn = psycopg.connect(host=host, dbname=DATABASES[branch], user=user, password=token,
                           sslmode="require", options="-c default_transaction_read_only=on")
    conn.read_only = True
    conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    return conn


def oracle_connect(secret_name, dsn_override):
    """Accepts JSON {user,password,dsn}, EZConnect user/password@host:port/service, or oracle://."""
    raw = os.environ[secret_name].strip()
    if raw.startswith("{"):
        cfg = json.loads(raw)
        user, password = cfg.get("user") or cfg["username"], cfg["password"]
        dsn = cfg.get("dsn") or f'{cfg["host"]}:{cfg.get("port", 1521)}/{cfg.get("service") or cfg["service_name"]}'
    else:
        creds, dsn = raw.removeprefix("oracle://").rsplit("@", 1)
        user, password = creds.split("/", 1) if "/" in creds else creds.split(":", 1)
    return oracledb.connect(user=user, password=password, dsn=dsn_override or dsn,
                            tcp_connect_timeout=15)


def _csv_value(v):
    if v is None:
        return ""
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S.%f")
    return str(v)


def _write_csv(cur, table):
    rows = cur.fetchall()
    out_dir = SNAPSHOT_DIR.with_name("snapshot.partial") / table
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{table}.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([d.name for d in cur.description])
        writer.writerows([_csv_value(v) for v in r] for r in rows)
    print(f"{table}: {len(rows)} rows")


def snapshot():
    # One REPEATABLE READ transaction, so all six files come from the same revision;
    # build/snapshot is replaced only once every export has succeeded, and the old
    # export stays in build/snapshot.previous until the new one is in place.
    partial = SNAPSHOT_DIR.with_name("snapshot.partial")
    shutil.rmtree(partial, ignore_errors=True)
    with lakebase_read_only(SOURCE_BRANCH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, code, included_units, overage_rate FROM ow_tp_invoicing.plans")
        _write_csv(cur, "plans")
        cur.execute("SELECT id, name FROM ow_tp_invoicing.tenants")
        _write_csv(cur, "tenants")
        cur.execute("SELECT id, tenant_id, plan_id, starts_on, ends_on, status_cd, suspended_on FROM ow_tp_invoicing.subscriptions")
        _write_csv(cur, "subscriptions")
        cur.execute("SELECT id, tenant_id, occurred_at, units, kind_cd FROM ow_tp_invoicing.usage_events")
        _write_csv(cur, "usage_events")
        cur.execute("SELECT id, tenant_id, period_start, period_end FROM ow_tp_invoicing.rating_periods")
        _write_csv(cur, "rating_periods")
        cur.execute("SELECT id, period_id, rollover_units FROM ow_tp_invoicing.rating_results")
        _write_csv(cur, "rating_results")
    previous = SNAPSHOT_DIR.with_name("snapshot.previous")
    shutil.rmtree(previous, ignore_errors=True)
    if SNAPSHOT_DIR.exists():
        SNAPSHOT_DIR.rename(previous)
    partial.rename(SNAPSHOT_DIR)
    shutil.rmtree(previous)


def _norm(row):
    out = []
    for v in row:
        if isinstance(v, datetime.datetime):
            v = v.date()
        if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
            v = Decimal(str(v)).normalize()
        elif isinstance(v, str):
            try:
                v = Decimal(v).normalize()
            except ArithmeticError:
                pass
        out.append("" if v is None else format(v, "f") if isinstance(v, Decimal) else str(v))
    return out


def parity():
    out = subprocess.check_output([
        "databricks", "experimental", "aitools", "tools", "query", "--warehouse", WAREHOUSE_ID,
        "--output", "json",
        "SELECT tenant_id, period_start, period_end, subscription_id, plan_id, plan_code,"
        " event_count, used_units, quota_units, rollover_units, billable_units,"
        " first_tier_units, second_tier_units, overage_amount"
        " FROM ow_tp.ow_tp_usage_meter.ow_tp_usage_meter ORDER BY tenant_id, period_start"])
    result = json.loads(out)
    rows = result["rows"] if isinstance(result, dict) else result
    delta = sorted(_norm([r[c] for c in METER_COLUMNS] if isinstance(r, dict) else r) for r in rows)
    with lakebase_read_only(METER_BRANCH) as conn:
        cur = conn.cursor()
        cur.execute("""SELECT tenant_id, period_start, period_end, subscription_id, plan_id, plan_code,
                              event_count, used_units, quota_units, rollover_units, billable_units,
                              first_tier_units, second_tier_units, overage_amount
                         FROM ow_tp_usage_meter.ow_tp_usage_meter_synced
                        ORDER BY tenant_id, period_start""")
        lakebase = sorted(_norm(r) for r in cur.fetchall())
    only_delta = [r for r in delta if r not in lakebase]
    only_lakebase = [r for r in lakebase if r not in delta]
    print(f"Delta rows: {len(delta)}; Lakebase rows: {len(lakebase)}; "
          f"only in Delta: {len(only_delta)}; only in Lakebase: {len(only_lakebase)}")
    for r in (only_delta + only_lakebase)[:5]:
        print("  diff:", r)
    match = delta == lakebase and bool(delta)
    print("MATCH" if match else "MISMATCH")
    return 0 if match else 1


def compare(tenant, secret_name, dsn_override):
    # pkg_rating.compute_rating re-derived in plain SQL against OW_BILLING (the
    # read-only principal has no EXECUTE on the package).
    with oracle_connect(secret_name, dsn_override) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM ow_billing.tenants WHERE name = :n", n=tenant)
        (tenant_id,), = cur.fetchall()
        cur.execute("""
WITH t AS (SELECT id FROM ow_billing.tenants WHERE id = :tenant_id),
rp AS (
    SELECT rp.tenant_id, TRUNC(rp.period_start) AS ps, TRUNC(rp.period_end) AS pe
      FROM ow_billing.rating_periods rp JOIN t ON t.id = rp.tenant_id
),
uncovered AS (
    SELECT DISTINCT u.tenant_id, TRUNC(u.occurred_at) AS d
      FROM ow_billing.usage_events u JOIN t ON t.id = u.tenant_id
     WHERE NOT EXISTS (
           SELECT 1 FROM rp
            WHERE rp.tenant_id = u.tenant_id AND TRUNC(u.occurred_at) BETWEEN rp.ps AND rp.pe)
),
gaps AS (
    SELECT x.tenant_id,
           NVL(MAX(CASE WHEN rp.pe < x.d AND rp.pe >= TRUNC(x.d, 'MM') THEN rp.pe + 1 END),
               TRUNC(x.d, 'MM')) AS ps,
           NVL(MIN(CASE WHEN rp.ps > x.d AND rp.ps <= LAST_DAY(x.d) THEN rp.ps - 1 END),
               LAST_DAY(x.d)) AS pe
      FROM uncovered x LEFT JOIN rp ON rp.tenant_id = x.tenant_id
     GROUP BY x.tenant_id, x.d
),
periods AS (
    SELECT tenant_id, ps, pe FROM rp
    UNION
    SELECT tenant_id, ps, pe FROM gaps
),
base AS (
    SELECT p.ps, p.pe, s.status_cd, TRUNC(s.suspended_on) AS suspended_on,
           pl.code AS plan_code, pl.included_units AS included, pl.overage_rate AS rate,
           (SELECT COUNT(*) FROM ow_billing.usage_events u
             WHERE u.tenant_id = p.tenant_id
               AND TO_CHAR(u.occurred_at, 'YYYYMMDD')
                   BETWEEN TO_CHAR(p.ps, 'YYYYMMDD') AND TO_CHAR(p.pe, 'YYYYMMDD')) AS event_count,
           (SELECT NVL(SUM(u.units), 0) FROM ow_billing.usage_events u
             WHERE u.tenant_id = p.tenant_id
               AND TO_CHAR(u.occurred_at, 'YYYYMMDD')
                   BETWEEN TO_CHAR(p.ps, 'YYYYMMDD') AND TO_CHAR(p.pe, 'YYYYMMDD')) AS used,
           (SELECT NVL(SUM(rr.rollover_units), 0)
              FROM ow_billing.rating_results rr, ow_billing.rating_periods rp
             WHERE rp.id = rr.period_id AND rp.tenant_id = p.tenant_id
               AND rp.period_start < p.ps
               AND rp.period_start >= ADD_MONTHS(p.ps, -3)) AS banked
      FROM periods p
      OUTER APPLY (
           SELECT s.plan_id, s.status_cd, s.suspended_on FROM ow_billing.subscriptions s
            WHERE s.tenant_id = p.tenant_id AND s.starts_on <= p.pe
              AND (s.ends_on IS NULL OR s.ends_on >= p.ps)
            ORDER BY s.starts_on DESC FETCH FIRST 1 ROWS ONLY) s
      LEFT JOIN ow_billing.plans pl ON pl.id = s.plan_id
),
rated AS (
    SELECT b.*, LEAST(NVL(2 * b.included, b.banked), b.banked) AS rollover
      FROM base b
),
billed AS (
    SELECT r.*, GREATEST(NVL(r.used - r.rollover - r.included, 0), 0) AS billable_raw
      FROM rated r
),
tiered AS (
    SELECT b.*, LEAST(b.billable_raw, 101) AS first_tier,
           GREATEST(b.billable_raw - 101, 0) AS second_tier,
           ROUND(LEAST(b.billable_raw, 101) * b.rate
                 + GREATEST(b.billable_raw - 101, 0) * b.rate * 1.5, 2) AS overage_raw,
           CASE WHEN b.status_cd = 20 AND b.suspended_on BETWEEN b.ps AND b.pe
                THEN (b.pe - b.suspended_on + 1) / (b.pe - b.ps + 1) END AS factor
      FROM billed b
)
SELECT ps, pe, plan_code, event_count, used, included, rollover,
       CASE WHEN factor IS NULL THEN billable_raw ELSE ROUND(billable_raw * factor) END,
       first_tier, second_tier,
       CASE WHEN factor IS NULL THEN overage_raw ELSE ROUND(overage_raw * factor, 2) END
  FROM tiered
 ORDER BY ps
""", tenant_id=tenant_id)
        oracle = [_norm(r) for r in cur.fetchall()]
    with lakebase_read_only(METER_BRANCH) as conn:
        cur = conn.cursor()
        cur.execute("""SELECT period_start, period_end, plan_code, event_count, used_units, quota_units,
                              rollover_units, billable_units, first_tier_units, second_tier_units,
                              overage_amount
                         FROM ow_tp_usage_meter.ow_tp_usage_meter_synced
                        WHERE tenant_id = %s
                        ORDER BY period_start""", (tenant_id,))
        meter = [_norm(r) for r in cur.fetchall()]
    print(f"Tenant: {tenant} ({tenant_id})\n")
    print("| source | " + " | ".join(COLUMNS) + " |")
    print("|" + "---|" * (len(COLUMNS) + 1))
    for name, rows in (("Lakebase meter", meter), ("Oracle OW_BILLING", oracle)):
        for r in rows:
            print(f"| {name} | " + " | ".join(r) + " |")
    match = meter == oracle and bool(meter)
    print(f"\n{'MATCH' if match else 'MISMATCH'}: {len(meter)} meter periods vs {len(oracle)} Oracle periods")
    return 0 if match else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot")
    sub.add_parser("parity")
    cp = sub.add_parser("compare")
    cp.add_argument("--tenant", default="Tenant One")
    cp.add_argument("--oracle-secret", default="OW_TP_ORACLE_RO_DSN")
    cp.add_argument("--oracle-dsn", help="host:port/service, overrides the secret's address")
    args = ap.parse_args()
    if args.cmd == "snapshot":
        snapshot()
    elif args.cmd == "parity":
        sys.exit(parity())
    else:
        sys.exit(compare(args.tenant, args.oracle_secret, args.oracle_dsn))


if __name__ == "__main__":
    main()
