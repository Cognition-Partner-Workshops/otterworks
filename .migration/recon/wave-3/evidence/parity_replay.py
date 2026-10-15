"""Replay the read-only invoicing/dunning parity scenarios (INVOICE-001, INVOICE-002, INVOICE-006,
DUNNING-001) myself. Legacy side: the function bodies re-expressed as SELECTs (fn_usage_rating inlined
as in the wave-2 replay) run under billing_ro (SELECT only, no EXECUTE) on the live fixture. Target
side: the equivalent reads on Atlas billing_migration with the arithmetic of invoicing.sql /
dunning.sql mirrored here (not the billing-service code). Legacy and target are compared field by
field, and the pinned business-field subset against the committed transcripts. The write scenarios
(INVOICE-003/004/005, DUNNING-002..005) are replayed in writes_replay.py on the disposable stack."""
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

FIRST_TIER, SECOND_MULT, CENTS, TAX_RATE = 101, Decimal("1.5"), Decimal("0.01"), Decimal("0.0825")
def q2(v): return str(Decimal(str(v)).quantize(CENTS, rounding=ROUND_HALF_UP))
def rhu0(v): return int(Decimal(str(v)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
def months_before(d, n):
    y, m = d.year, d.month - n
    while m <= 0: y -= 1; m += 12
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))
def utc_date(v): return v.astimezone(timezone.utc).date()
def D(v): return v.to_decimal() if hasattr(v, "to_decimal") else Decimal(str(v))

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
    plan.included_units, plan.overage_rate, plan.monthly_fee, plan.code,
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
SELECT code, monthly_fee, CASE WHEN prorate THEN round(amount0 * factor, 2) ELSE amount0 END AS overage_amount,
  (SELECT tax_exempt FROM billing.tenants WHERE id = %(t)s) AS tax_exempt,
  (SELECT COALESCE(sum(remaining_amount), 0) FROM billing.credit_notes WHERE tenant_id = %(t)s AND remaining_amount > 0) AS credit
FROM amt
"""

def preview_lines(code, fee, overage, tax_exempt, credit):
    """fn_invoice_preview's RETURN QUERY, mirrored. Returns rows of (line_no, line_type, description, amount, tax_amount, credit_applied, total) as strings."""
    fee, overage, credit = D(fee), D(overage), D(credit)
    tax = Decimal(0) if tax_exempt else (fee + overage) * TAX_RATE
    cap = min(credit, Decimal(q2(fee + overage + tax)))
    rows = [(1, "plan", code, q2(fee), "0.00", "0.00", q2(fee)),
            (2, "usage", "usage overage", q2(overage), "0.00", "0.00", q2(overage)),
            (3, "tax", "regional tax", q2(tax / 2), "0.00", "0.00", q2(tax / 2)),
            (4, "tax", "local tax", q2(tax / 2), "0.00", "0.00", q2(tax / 2)),
            (5, "credit", "credit notes", "0.00", "0.00", q2(cap), q2(-cap))]
    return [dict(zip(("line_no", "line_type", "description", "amount", "tax_amount", "credit_applied", "total"), r)) for r in rows]

def legacy_preview(t, ps, pe):
    r = pg.execute(LEGACY_RATING, {"t": t, "ps": ps, "pe": pe}).fetchone()
    return None if r is None else preview_lines(r["code"], r["monthly_fee"], r["overage_amount"], r["tax_exempt"], r["credit"])

def target_rating(t, ps, pe):
    subs = [s for s in db.subscriptions.find({"tenantId": t}) if utc_date(s["startsOn"]) <= pe and ("endsOn" not in s or utc_date(s["endsOn"]) >= ps)]
    if not subs: return None
    sub = max(subs, key=lambda s: s["startsOn"])
    plan = db.plans.find_one({"_id": sub["planId"]})
    included, rate = int(plan["includedUnits"]), D(plan["overageRate"])
    used = sum(int(u["units"]) for u in db.usageEvents.find({"tenantId": t}) if ps <= utc_date(u["occurredAt"]) <= pe)
    lo = months_before(ps, 3)
    prior = min(2 * included, sum(int(p["rating"]["rolloverUnits"]) for p in db.ratingPeriods.find({"tenantId": t}) if isinstance(p.get("rating"), dict) and lo <= utc_date(p["periodStart"]) < ps))
    rollover = min(prior, included * 2)
    billable = max(used - rollover - included, 0)
    first, second = min(billable, FIRST_TIER), max(billable - FIRST_TIER, 0)
    amount = Decimal(q2(first * rate + second * rate * SECOND_MULT))
    so = sub.get("suspendedOn")
    if sub["status"] == "suspended" and so is not None and ps <= utc_date(so) <= pe:
        factor = Decimal((pe - utc_date(so)).days + 1) / Decimal((pe - ps).days + 1)
        amount = Decimal(q2(amount * factor))
    return plan, amount

def target_preview(t, ps, pe):
    r = target_rating(t, ps, pe)
    if r is None: return None
    plan, overage = r
    tenant = db.tenants.find_one({"_id": t})
    credit = sum(D(n["remainingAmount"]) for n in tenant.get("creditNotes", []) if D(n["remainingAmount"]) > 0)
    return preview_lines(plan["code"], D(plan["monthlyFee"]), overage, bool(tenant["taxExempt"]), credit)

def legacy_lines(invoice_id):
    return [{"line_no": r["line_no"], "line_type": r["line_type"], "description": r["description"], "amount": q2(r["amount"])}
            for r in pg.execute("SELECT line_no, line_type, description, amount FROM billing.invoice_lines WHERE invoice_id = %(i)s ORDER BY line_no", {"i": invoice_id}).fetchall()]
def target_lines(invoice_id):
    d = db.invoices.find_one({"_id": invoice_id})
    return None if d is None else [{"line_no": e["lineNo"], "line_type": e["lineType"], "description": e["description"], "amount": q2(D(e["amount"]))}
                                   for e in sorted(d.get("invoiceLines", []), key=lambda e: e["lineNo"])]

def legacy_overdue(as_of):
    return [{"tenant_id": str(r["tenant_id"]), "invoice_id": str(r["invoice_id"]), "total": q2(r["total"]), "days_overdue": int(r["days_overdue"]), "tenant_status": r["tenant_status"]}
            for r in pg.execute("SELECT i.tenant_id, i.id AS invoice_id, i.total, (%(d)s - i.issued_at::date)::integer AS days_overdue, t.status AS tenant_status FROM billing.invoices i JOIN billing.tenants t ON t.id = i.tenant_id WHERE i.status = 'overdue' AND i.issued_at::date < %(d)s ORDER BY i.issued_at, i.id", {"d": as_of}).fetchall()]
def target_overdue(as_of):
    rows = []
    for d in sorted(db.invoices.find({"status": "overdue"}), key=lambda d: (d["issuedAt"], d["_id"].int)):
        if utc_date(d["issuedAt"]) >= as_of: continue
        t = db.tenants.find_one({"_id": d["tenantId"]}, {"status": 1})
        if t is None: continue
        rows.append({"tenant_id": str(d["tenantId"]), "invoice_id": str(d["_id"]), "total": q2(D(d["total"])), "days_overdue": (as_of - utc_date(d["issuedAt"])).days, "tenant_status": t["status"]})
    return rows

def collect(rows, field): return [r[field] for r in rows]
PINNED = {  # transcript business_fields -> how to derive them from the replayed rows
    "INVOICE-001": lambda rows: {"line_numbers": collect(rows, "line_no"), "amounts": collect(rows, "amount"), "totals": collect(rows, "total")},
    "INVOICE-002": lambda rows: {"line_types": collect(rows, "line_type"), "tax_amount": collect(rows, "tax_amount")},
    "INVOICE-006": lambda rows: {"line_types": collect(rows, "line_type"), "amounts": collect(rows, "amount")},
    "DUNNING-001": lambda rows: {"tenant_ids": collect(rows, "tenant_id"), "days_overdue": collect(rows, "days_overdue")},
}
results = {"pg_session_timezone": pg.execute("SHOW TimeZone").fetchone()["TimeZone"]}
for f in sorted(glob.glob("procs/transcripts/invoicing/*.json") + glob.glob("procs/transcripts/dunning/*.json")):
    tr = json.load(open(f)); sid = tr["scenario"]
    if sid not in PINNED:
        results[sid] = {"entrypoint": tr["entrypoint"], "replayed_here": False, "reason": "write scenario; replayed on the disposable procs stack in writes_replay.py and by the procs harness"}
        continue
    inp = tr["inputs"]
    if tr["entrypoint"] == "billing.fn_invoice_preview":
        args = (UUID(inp["tenant_id"]), date.fromisoformat(inp["period_start"]), date.fromisoformat(inp["period_end"]))
        legacy, target = legacy_preview(*args), target_preview(*args)
    elif tr["entrypoint"] == "billing.fn_invoice_lines":
        legacy, target = legacy_lines(UUID(inp["invoice_id"])), target_lines(UUID(inp["invoice_id"]))
    else:
        legacy, target = legacy_overdue(date.fromisoformat(inp["as_of"])), target_overdue(date.fromisoformat(inp["as_of"]))
    pinned = tr["business_fields"]
    results[sid] = {"entrypoint": tr["entrypoint"], "inputs": inp, "legacy": legacy, "target": target, "transcript": pinned,
                    "legacy_eq_target": legacy == target, "target_eq_transcript": PINNED[sid](target or []) == pinned,
                    "compared_fields_legacy_vs_target": sorted(legacy[0]) if legacy else None, "rows": len(legacy or [])}
done = [s for s in PINNED]
results["summary"] = {"scenarios_replayed": done, "all_legacy_eq_target": all(results[s]["legacy_eq_target"] for s in done), "all_target_eq_transcript": all(results[s]["target_eq_transcript"] for s in done)}
print(json.dumps(results, indent=1, default=str))
