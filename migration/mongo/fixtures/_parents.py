#!/usr/bin/env python3
"""Shared parent-row helpers for wave-2 fixture seeders.

Each wave-2 unit seeds child tables whose FKs point at rows owned by
another unit's seeder (tenants, plans, subscriptions, rating_periods,
invoices). These helpers MERGE the canonical parent rows in if missing,
so a seeder runs on a fresh fixture. Values are deterministic and identical
to what the owning seeder inserts for the same id, so the owning seeder's
own DELETE+INSERT is unaffected; parents are never deleted here.

Oracle only, same local-only pattern as the seeders (_local.require_local_dsn
is exercised by callers; nothing here touches Mongo).
"""

from __future__ import annotations

import datetime as dt

TENANTS = [
    ("SYNTH-TEN-1", "Synth Tenant One", "Y", 10),
    ("SYNTH-TEN-2", "Synth Tenant Two", "N", 10),
    ("SYNTH-TEN-3", "Synth Tenant Three", "N", 999),
]
TENANT_ROWS = {t[0]: t for t in TENANTS}

PLANS = [
    ("SYNTH-PLAN-A", "SYNTH-A", 1, "0.00", 0, "0.000000", "Y"),
    ("SYNTH-PLAN-B", "SYNTH-B", 999, "999999.99", 1000000, "1.234567", "Y"),
    ("SYNTH-PLAN-C", "SYNTH-C", 2, "49.95", 100, "0.050000", "N"),
]
PLAN_ROWS = {p[0]: p for p in PLANS}

SUBSCRIPTIONS = [
    ("SYNTH-SUB-OPEN", "SYNTH-TEN-1", "SYNTH-PLAN-A",
     dt.date(2026, 1, 1), None, 10, None),
    ("SYNTH-SUB-CLOSED", "SYNTH-TEN-1", "SYNTH-PLAN-B",
     dt.date(2025, 1, 1), dt.date(2025, 12, 31), 20, None),
    ("SYNTH-SUB-CXL", "SYNTH-TEN-2", "SYNTH-PLAN-A",
     dt.date(2024, 6, 1), dt.date(2024, 9, 1), 30, None),
    ("SYNTH-SUB-SUSP", "SYNTH-TEN-2", "SYNTH-PLAN-B",
     dt.date(2026, 3, 1), None, 10, dt.date(2026, 7, 15)),
    ("SYNTH-SUB-UNKNOWN", "SYNTH-TEN-3", "SYNTH-PLAN-B",
     dt.date(2026, 2, 2), None, 42, None),
]
SUBSCRIPTION_ROWS = {s[0]: s for s in SUBSCRIPTIONS}

_AMTS = ["0.01", "0.05", "9999999999.99", "123.45", "100.00", "0.99"]


def _rp_row(i: int):
    """Canonical SYNTH-RP-i row, identical to seed_usage_rating."""
    start = dt.date(2026, (i // 3) + 1, (i % 3) * 9 + 1)
    return (f"SYNTH-RP-{i:04d}", TENANTS[i % 3][0], start,
            start + dt.timedelta(days=25))


def _iv_row(i: int):
    """Canonical SYNTH-IV-i row, identical to seed_invoicing."""
    return (f"SYNTH-IV-{i:04d}", TENANTS[i % 3][0], f"SYNTH-RP-{i % 30:04d}",
            dt.datetime(2026, (i % 9) + 1, (i % 27) + 1, 12, 0, 0,
                        ((i * 211) % 1000) * 1000),
            float(_AMTS[i % 6]), float(_AMTS[(i + 1) % 6]),
            float(_AMTS[(i + 2) % 6]), [0, 1, 2, 3, 55][i % 5])


def ensure_tenants(cur, ids, values=None):
    """MERGE tenant parents for `ids`. `values` optionally overrides a
    non-canonical id with an explicit (id, name, tax_exempt_yn, status_cd)."""
    values = values or {}
    for tid in ids:
        row = values.get(tid) or TENANT_ROWS.get(tid) or (tid, tid, "N", 10)
        cur.execute(
            """MERGE INTO tenants t
               USING (SELECT :1 id, :2 name, :3 tax_exempt_yn, :4 status_cd
                      FROM dual) s
               ON (t.id = s.id)
               WHEN NOT MATCHED THEN INSERT (id, name, tax_exempt_yn, status_cd)
                   VALUES (s.id, s.name, s.tax_exempt_yn, s.status_cd)""",
            row)


def ensure_plan(cur, pid):
    row = PLAN_ROWS[pid]
    cur.execute(
        """MERGE INTO plans t
           USING (SELECT :1 id, :2 code, :3 tier_cd, :4 monthly_fee,
                        :5 included_units, :6 overage_rate, :7 active_yn
                  FROM dual) s
           ON (t.id = s.id)
           WHEN NOT MATCHED THEN INSERT (id, code, tier_cd, monthly_fee,
               included_units, overage_rate, active_yn)
               VALUES (s.id, s.code, s.tier_cd, s.monthly_fee,
                       s.included_units, s.overage_rate, s.active_yn)""",
        row)


def ensure_subscriptions(cur, ids, values=None):
    """MERGE subscription parents (with their tenant/plan parents first).
    `values` may override a non-canonical id with an explicit row tuple."""
    values = values or {}
    for sid in ids:
        row = values.get(sid) or SUBSCRIPTION_ROWS.get(sid) or (
            sid, "SYNTH-TEN-1", "SYNTH-PLAN-A",
            dt.date(2026, 1, 1), None, 10, None)
        ensure_tenants(cur, [row[1]])
        ensure_plan(cur, row[2])
        cur.execute(
            """MERGE INTO subscriptions t
               USING (SELECT :1 id, :2 tenant_id, :3 plan_id, :4 starts_on,
                            :5 ends_on, :6 status_cd, :7 suspended_on
                      FROM dual) s
               ON (t.id = s.id)
               WHEN NOT MATCHED THEN INSERT (id, tenant_id, plan_id, starts_on,
                   ends_on, status_cd, suspended_on)
                   VALUES (s.id, s.tenant_id, s.plan_id, s.starts_on,
                           s.ends_on, s.status_cd, s.suspended_on)""",
            row)


def ensure_rating_periods(cur, ids, values=None):
    """MERGE rating_periods parents (tenants first). `values` may override a
    non-canonical id with an explicit (id, tenant_id, start, end) tuple."""
    values = values or {}
    for pid in ids:
        try:
            row = values.get(pid) or _rp_row(int(pid.rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            row = (pid, "SYNTH-TEN-1", dt.date(2026, 1, 1),
                   dt.date(2026, 1, 26))
        ensure_tenants(cur, [row[1]])
        cur.execute(
            """MERGE INTO rating_periods t
               USING (SELECT :1 id, :2 tenant_id, :3 period_start,
                            :4 period_end FROM dual) s
               ON (t.id = s.id)
               WHEN NOT MATCHED THEN INSERT (id, tenant_id, period_start,
                   period_end)
                   VALUES (s.id, s.tenant_id, s.period_start, s.period_end)""",
            row)


def ensure_invoices(cur, ids, values=None):
    """MERGE invoice parents (each invoice's period + tenant parents first).
    `values` may override a non-canonical id with an explicit row tuple."""
    values = values or {}
    for iid in ids:
        try:
            row = values.get(iid) or _iv_row(int(iid.rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            row = values.get(iid) or (
                iid, "SYNTH-TEN-1", "SYNTH-RP-0000",
                dt.datetime(2026, 1, 1), 0.01, 0.05, 0.06, 0)
        ensure_tenants(cur, [row[1]])
        ensure_rating_periods(cur, [row[2]])
        cur.execute(
            """MERGE INTO invoices t
               USING (SELECT :1 id, :2 tenant_id, :3 period_id, :4 issued_at,
                            :5 subtotal, :6 tax, :7 total, :8 status_cd
                      FROM dual) s
               ON (t.id = s.id)
               WHEN NOT MATCHED THEN INSERT (id, tenant_id, period_id,
                   issued_at, subtotal, tax, total, status_cd)
                   VALUES (s.id, s.tenant_id, s.period_id, s.issued_at,
                           s.subtotal, s.tax, s.total, s.status_cd)""",
            row)
