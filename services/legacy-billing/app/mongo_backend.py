"""MongoDB read backend for the billing routes.

Serves the same JSON shapes as the PostgreSQL `billing.fn_*` entrypoints from the
`ow_billing` document model (map-1). Status codes are resolved through the `codes`
reference collection; numeric values keep PostgreSQL's numeric display scale so the
two backends diff clean. Write routes are not implemented here: the history triggers
and `sp_*` procedures stay on the relational side until a customer run.
"""

import calendar
import os
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache

from bson.decimal128 import Decimal128
from pymongo import MongoClient

TAX_RATE = Decimal("0.0825")
MIN_SIG_DIGITS = 16


@lru_cache(maxsize=1)
def client():
    return MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))


def db():
    return client()[os.getenv("MONGO_DB", "ow_billing")]


def ping():
    client().admin.command("ping")


def dec(value):
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def scaled(value, scale):
    q = Decimal(1).scaleb(-scale)
    out = dec(value).quantize(q, rounding=ROUND_HALF_UP)
    return out if out != 0 else Decimal(0).quantize(q)


def pg_div(a, b):
    """Divide with the display scale PostgreSQL's numeric division would choose."""
    a, b = dec(a), dec(b)
    weight_a, weight_b = _weight(a), _weight(b)
    qweight = weight_a - weight_b
    if _first_digit(a, weight_a) < _first_digit(b, weight_b):
        qweight -= 1
    rscale = max(MIN_SIG_DIGITS - 4 * qweight, -a.as_tuple().exponent, -b.as_tuple().exponent, 0)
    return (a / b).quantize(Decimal(1).scaleb(-rscale), rounding=ROUND_HALF_UP)


def _weight(x):
    digits = abs(x).adjusted() + 1
    return (digits - 1) // 4 if digits > 0 else -((-digits) // 4) - 1


def _first_digit(x, weight):
    return int(abs(x).scaleb(-4 * weight))


def num(value):
    if value is None:
        return None
    text = str(value)
    return text.lstrip("-") if value == 0 else text


def as_day(value):
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def as_dt(day):
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def codes(code_type):
    return {c["codeVal"]: c["codeDesc"] for c in db().codes.find({"codeType": code_type})}


def list_plans():
    tiers = codes("PLAN_TIER")
    plans = db().plans.find({"active": True})
    out = [
        {
            "plan_id": p["_id"],
            "code": p["code"],
            "tier": tiers.get(p["tierCd"], "UNKNOWN"),
            "monthly_fee": num(scaled(p["monthlyFee"], 2)),
            "included_units": p["includedUnits"],
            "overage_rate": num(scaled(p["overageRate"], 6)),
        }
        for p in plans
    ]
    return sorted(out, key=lambda r: (Decimal(r["monthly_fee"]), r["code"]))


def current_subscription(tenant_id, start, end):
    """Latest subscription overlapping [start, end], like the SQL ORDER BY starts_on DESC LIMIT 1."""
    subs = db().subscriptions.find({
        "tenantId": tenant_id,
        "startsOn": {"$lte": as_dt(end)},
        "$or": [{"endsOn": None}, {"endsOn": {"$exists": False}}, {"endsOn": {"$gte": as_dt(start)}}],
    }).sort("startsOn", -1).limit(1)
    return next(iter(subs), None)


def entitlement(tenant_id, on):
    on = as_day(on)
    tenant = db().tenants.find_one({"_id": tenant_id})
    sub = current_subscription(tenant_id, on, on)
    if tenant is None or sub is None:
        return []
    plan = db().plans.find_one({"_id": sub["planId"]})
    return [{
        "tenant_id": tenant["_id"],
        "plan_code": plan["code"],
        "tier": codes("PLAN_TIER").get(plan["tierCd"], "UNKNOWN"),
        "monthly_fee": num(scaled(plan["monthlyFee"], 2)),
        "included_units": plan["includedUnits"],
        "subscription_status": codes("SUB_STATUS").get(sub["statusCd"], "UNKNOWN"),
        "effective_on": str(max(as_day(sub["startsOn"]), on)),
    }]


def usage_rating(tenant_id, start, end):
    start, end = as_day(start), as_day(end)
    sub = current_subscription(tenant_id, start, end)
    plan = db().plans.find_one({"_id": sub["planId"]}) if sub else None
    included = plan["includedUnits"] if plan else None
    rate = dec(plan["overageRate"]) if plan else None

    used = sum(
        u.get("units", 0)
        for u in db().usageEvents.find({
            "tenantId": tenant_id,
            "occurredAt": {"$gte": as_dt(start), "$lt": as_dt(end) + timedelta(days=1)},
        })
    )
    three_months_back = as_dt(_minus_months(start, 3))
    period_ids = [
        p["_id"] for p in db().ratingPeriods.find({
            "tenantId": tenant_id,
            "periodStart": {"$lt": as_dt(start), "$gte": three_months_back},
        })
    ]
    prior_sum = sum(
        r.get("rolloverUnits", 0) for r in db().ratingResults.find({"periodId": {"$in": period_ids}})
    )
    # PostgreSQL LEAST/GREATEST skip NULL operands, so a tenant with no covering
    # subscription still rates: null quota and amount, zero billable units.
    if plan is None:
        rollover, billable, first, second, amount = prior_sum, 0, 0, 0, None
    else:
        prior = min(2 * included, prior_sum)
        rollover = min(prior, included * 2)
        billable = max(used - rollover - included, 0)
        first = min(billable, 101)
        second = max(billable - 101, 0)
        amount = scaled(first * rate + second * rate * Decimal("1.5"), 2)

    suspended_on = sub.get("suspendedOn") if sub else None
    if sub and sub.get("statusCd") == 20 and suspended_on is not None \
            and start <= as_day(suspended_on) <= end:
        fraction = Decimal((end - as_day(suspended_on)).days + 1) / Decimal((end - start).days + 1)
        billable = int((Decimal(billable) * fraction).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        amount = scaled(amount * fraction, 2)

    return {
        "tenant_id": tenant_id,
        "period_start": str(start),
        "period_end": str(end),
        "used_units": used,
        "quota_units": included,
        "rollover_units": rollover,
        "billable_units": billable,
        "first_tier_units": first,
        "second_tier_units": second,
        "overage_amount": amount,
        "_plan": plan,
    }


def _minus_months(day, months):
    month = day.month - months
    year = day.year
    while month <= 0:
        month += 12
        year -= 1
    last = calendar.monthrange(year, month)[1]
    return day.replace(year=year, month=month, day=min(day.day, last))


def invoice_preview(tenant_id, start, end):
    rating = usage_rating(tenant_id, start, end)
    plan = rating["_plan"]
    fee = dec(plan["monthlyFee"]) if plan else None
    overage = rating["overage_amount"]
    open_notes = [
        dec(c["remainingAmount"]) for c in db().creditNotes.find(
            {"tenantId": tenant_id, "remainingAmount": {"$gt": Decimal128("0")}})
    ]
    credit = scaled(sum(open_notes), 2) if open_notes else Decimal(0)
    tenant = db().tenants.find_one({"_id": tenant_id}) or {}
    if tenant.get("taxExempt"):
        tax = Decimal(0)
    elif plan is None:
        tax = None
    else:
        tax = (fee + overage) * TAX_RATE
    half_tax = pg_div(tax, 2) if tax is not None else None
    # LEAST(credit, NULL) is credit in PostgreSQL
    if plan is None:
        credit_applied = credit
    else:
        credit_applied = min(credit, scaled(fee + overage + tax, 2))
    zero = Decimal(0)
    code = plan["code"] if plan else None
    fee2 = scaled(fee, 2) if plan else None
    overage2 = scaled(overage, 2) if plan else None

    def line(no, kind, desc, amount, applied, total):
        return {
            "line_no": no, "line_type": kind, "description": desc,
            "amount": num(amount), "tax_amount": num(zero),
            "credit_applied": num(applied), "total": num(total),
        }

    return [
        line(1, "plan", code, fee2, zero, fee2),
        line(2, "usage", "usage overage", overage2, zero, overage2),
        line(3, "tax", "regional tax", half_tax, zero, half_tax),
        line(4, "tax", "local tax", half_tax, zero, half_tax),
        line(5, "credit", "credit notes", zero, credit_applied, -credit_applied),
    ]


def invoice_lines(invoice_id):
    inv = db().invoices.find_one({"_id": invoice_id}, {"lines": 1})
    if not inv:
        return []
    return [
        {
            "line_no": l["lineNo"],
            "line_type": l["lineType"],
            "description": l.get("description"),
            "amount": num(scaled(l["amount"], 2)),
        }
        for l in sorted(inv.get("lines", []), key=lambda l: l["lineNo"])
    ]


def overdue_accounts(as_of):
    as_of = as_day(as_of)
    statuses = codes("TENANT_STATUS")
    inv_status = {v: k for k, v in codes("INV_STATUS").items()}
    overdue_cd = inv_status.get("overdue", 40)
    rows = []
    for inv in db().invoices.find(
        {"statusCd": overdue_cd, "issuedAt": {"$lt": as_dt(as_of)}}
    ).sort([("issuedAt", 1), ("_id", 1)]):
        tenant = db().tenants.find_one({"_id": inv["tenantId"]})
        if tenant is None:
            continue
        rows.append({
            "tenant_id": inv["tenantId"],
            "invoice_id": inv["_id"],
            "total": num(scaled(inv["total"], 2)),
            "days_overdue": (as_of - as_day(inv["issuedAt"])).days,
            "tenant_status": statuses.get(tenant["statusCd"], "UNKNOWN"),
        })
    return rows
