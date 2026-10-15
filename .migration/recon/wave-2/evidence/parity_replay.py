"""Replay the read-only rating parity scenarios (RATING-001..007) myself.
Legacy side: the bodies of fn_usage_rating / fn_usage_summary re-expressed as one SELECT each and run
under billing_ro (SELECT only, no EXECUTE) on the live fixture. Target side: the equivalent reads on
Atlas billing_migration with the arithmetic of rating.sql mirrored here (not the billing-service code).
Both are compared column by column, and the business-field subset against the committed transcripts.
RATING-008 (sp_finalize_rating) is a write and is exercised only by the procs harness on the local stack."""
import calendar, glob, json, os
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient

pg_params = json.loads(os.environ["POSTGRESQL_RO_DSN"]); pg_params.pop("schema", None)
pg_params["dbname"] = pg_params.pop("database")
pg = psycopg.connect(**pg_params, row_factory=dict_row, autocommit=True, options="-c default_transaction_read_only=on")
db = MongoClient(os.environ["MONGODB_ATLAS_URI"], uuidRepresentation="standard", tz_aware=True)["billing_migration"]

FIRST_TIER, SECOND_MULT, CENTS = 101, Decimal("1.5"), Decimal("0.01")
def q2(v): return str(Decimal(str(v)).quantize(CENTS, rounding=ROUND_HALF_UP))
def rhu0(v): return int(Decimal(str(v)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
def months_before(d, n):  # PostgreSQL date - interval 'n months' (day clamped to month end)
    y, m = d.year, d.month - n
    while m <= 0: y -= 1; m += 12
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))
def utc_date(v): return v.astimezone(timezone.utc).date()

LEGACY_RATING = """
WITH sub AS (
  SELECT s.* FROM billing.subscriptions s
  WHERE s.tenant_id = %(t)s AND s.starts_on <= %(pe)s AND (s.ends_on IS NULL OR s.ends_on >= %(ps)s)
  ORDER BY s.starts_on DESC LIMIT 1),
plan AS (SELECT p.* FROM billing.plans p JOIN sub ON p.id = sub.plan_id),
base AS (
  SELECT
    (SELECT COALESCE(sum(u.units), 0)::integer FROM billing.usage_events u
      WHERE u.tenant_id = %(t)s AND u.occurred_at::date BETWEEN %(ps)s AND %(pe)s) AS used_units,
    plan.included_units, plan.overage_rate,
    LEAST(LEAST(2 * plan.included_units,
      (SELECT COALESCE(sum(rr.rollover_units), 0) FROM billing.rating_results rr
        JOIN billing.rating_periods rp ON rp.id = rr.period_id
        WHERE rp.tenant_id = %(t)s AND rp.period_start < %(ps)s
          AND rp.period_start >= %(ps)s::date - interval '3 months'))::integer, plan.included_units * 2) AS rollover_units,
    sub.status, sub.suspended_on
  FROM plan, sub),
calc AS (SELECT *, GREATEST(used_units - rollover_units - included_units, 0) AS billable0 FROM base),
tiers AS (SELECT *, LEAST(billable0, 101) AS first_tier_units, GREATEST(billable0 - 101, 0) AS second_tier_units FROM calc),
amt AS (
  SELECT *, round(first_tier_units * overage_rate + second_tier_units * overage_rate * 1.5, 2) AS amount0,
    (status = 'suspended' AND suspended_on IS NOT NULL AND suspended_on BETWEEN %(ps)s AND %(pe)s) AS prorate,
    ((%(pe)s::date - suspended_on + 1)::numeric / (%(pe)s::date - %(ps)s::date + 1)) AS factor
  FROM tiers)
SELECT used_units, included_units AS quota_units, rollover_units,
  CASE WHEN prorate THEN round(billable0 * factor)::integer ELSE billable0 END AS billable_units,
  first_tier_units, second_tier_units,
  CASE WHEN prorate THEN round(amount0 * factor, 2) ELSE amount0 END AS overage_amount
FROM amt
"""
LEGACY_SUMMARY = """
SELECT u.kind, count(*) AS event_count, COALESCE(sum(u.units), 0) AS units
FROM billing.usage_events u
WHERE u.tenant_id = %(t)s AND u.occurred_at::date BETWEEN %(ps)s AND %(pe)s
GROUP BY u.kind ORDER BY u.kind
"""

def legacy_rating(t, ps, pe):
    r = pg.execute(LEGACY_RATING, {"t": t, "ps": ps, "pe": pe}).fetchone()
    if r is None: return None
    return {k: (q2(v) if k == "overage_amount" else int(v)) for k, v in r.items()}

def target_rating(t, ps, pe):
    subs = [s for s in db.subscriptions.find({"tenantId": t})
            if utc_date(s["startsOn"]) <= pe and ("endsOn" not in s or utc_date(s["endsOn"]) >= ps)]
    if not subs: return None
    sub = max(subs, key=lambda s: s["startsOn"])
    plan = db.plans.find_one({"_id": sub["planId"]})
    included, rate = int(plan["includedUnits"]), plan["overageRate"].to_decimal()
    used = sum(int(u["units"]) for u in db.usageEvents.find({"tenantId": t}) if ps <= utc_date(u["occurredAt"]) <= pe)
    lo = months_before(ps, 3)
    prior = sum(int(p["rating"]["rolloverUnits"]) for p in db.ratingPeriods.find({"tenantId": t})
                if isinstance(p.get("rating"), dict) and lo <= utc_date(p["periodStart"]) < ps)
    prior = min(2 * included, prior)
    rollover = min(prior, included * 2)
    billable = max(used - rollover - included, 0)
    first, second = min(billable, FIRST_TIER), max(billable - FIRST_TIER, 0)
    amount = Decimal(str(q2(first * rate + second * rate * SECOND_MULT)))
    so = sub.get("suspendedOn")
    if sub["status"] == "suspended" and so is not None and ps <= utc_date(so) <= pe:
        factor = Decimal((pe - utc_date(so)).days + 1) / Decimal((pe - ps).days + 1)
        billable = rhu0(billable * factor)
        amount = Decimal(str(q2(amount * factor)))
    return {"used_units": used, "quota_units": included, "rollover_units": rollover, "billable_units": billable,
            "first_tier_units": first, "second_tier_units": second, "overage_amount": q2(amount)}

def legacy_summary(t, ps, pe):
    rows = pg.execute(LEGACY_SUMMARY, {"t": t, "ps": ps, "pe": pe}).fetchall()
    return {"kinds": [r["kind"] for r in rows], "event_counts": [int(r["event_count"]) for r in rows], "units": [int(r["units"]) for r in rows]}

def target_summary(t, ps, pe):
    agg = {}
    for u in db.usageEvents.find({"tenantId": t}):
        if ps <= utc_date(u["occurredAt"]) <= pe:
            c, s = agg.get(u["kind"], (0, 0)); agg[u["kind"]] = (c + 1, s + int(u["units"]))
    kinds = sorted(agg)
    return {"kinds": kinds, "event_counts": [agg[k][0] for k in kinds], "units": [agg[k][1] for k in kinds]}

transcripts = {}
for f in sorted(glob.glob("procs/transcripts/rating/RATING-00[1-7].json")):
    t = json.load(open(f)); transcripts[t["scenario"]] = t
results = {"pg_session_timezone": pg.execute("SHOW TimeZone").fetchone()["TimeZone"]}
for sid, tr in transcripts.items():
    inp = tr["inputs"]
    t, ps, pe = UUID(str(inp["tenant_id"])), date.fromisoformat(str(inp["period_start"])), date.fromisoformat(str(inp["period_end"]))
    if tr["entrypoint"] == "billing.fn_usage_summary":
        legacy, target = legacy_summary(t, ps, pe), target_summary(t, ps, pe)
    else:
        legacy, target = legacy_rating(t, ps, pe), target_rating(t, ps, pe)
    pinned = tr["business_fields"]
    subset = {k: v for k, v in (target or {}).items() if k in pinned}
    results[sid] = {"entrypoint": tr["entrypoint"], "inputs": inp, "legacy": legacy, "target": target, "transcript": pinned,
                    "legacy_eq_target": legacy == target, "target_eq_transcript": subset == pinned,
                    "compared_fields_legacy_vs_target": sorted(legacy) if legacy else None}
# RATING-008 (sp_finalize_rating, tenant 1, 2026-02) is a write scenario: confirm neither the live fixture
# nor Atlas carries that period, i.e. the harness replay on the local stack did not leak into the live data.
t1 = UUID("00000000-0000-0000-0000-000000000001")
results["RATING-008"] = {"entrypoint": "billing.sp_finalize_rating", "replayed_here": False,
    "reason": "write scenario; graded only by the procs harness on the local compose stack (evidence/procs_parity.json)",
    "live_fixture_has_2026-02_period_for_tenant_1": pg.execute("SELECT count(*) AS n FROM billing.rating_periods WHERE tenant_id = %(t)s AND period_start = %(ps)s", {"t": t1, "ps": date(2026, 2, 1)}).fetchone()["n"],
    "atlas_has_2026-02_period_for_tenant_1": db.ratingPeriods.count_documents({"tenantId": t1, "periodStart": datetime(2026, 2, 1, tzinfo=timezone.utc)})}
results["summary"] = {"scenarios_replayed": [s for s in results if s.startswith("RATING-00") and s != "RATING-008"],
                      "all_legacy_eq_target": all(results[s]["legacy_eq_target"] for s in results if s.startswith("RATING-00") and s != "RATING-008"),
                      "all_target_eq_transcript": all(results[s]["target_eq_transcript"] for s in results if s.startswith("RATING-00") and s != "RATING-008")}
print(json.dumps(results, indent=1, default=str))
