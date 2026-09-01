"""The OW_BILLING PL/SQL estate, converted to application code over MongoDB.

Five packages / 19 routines (`services/legacy-billing/db/oracle/packages/`) become the
functions below. The conversion is behaviour-preserving, not behaviour-improving: the tier
break at 101 units, the doubled `LEAST` cap, the credit burn-down that decrements a running
counter, and Oracle's NULL-propagating `LEAST`/`GREATEST` are all reproduced, because the
estate's recorded transcripts are the acceptance criteria and every one of those quirks is
observable in them. Improvements belong in a later change with its own evidence.

Package-state globals do not survive the conversion. `PKG_RATING` parked its intermediate
numbers in package variables so `PKG_INVOICING` could read them back on the next call --
two sessions rating the same tenant would have overwritten each other. Here the same
numbers are a returned `Rating` value, so the coupling is explicit and concurrency-safe.

Persistence is reached through the `Store` protocol (see `mongo_store.py`); the routines
themselves are free of driver calls so they can be graded against a dict-backed store as
well as against the migrated Atlas database.
"""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TAX_RATE = Decimal("0.0825")
TIER_BREAK = 101
SECOND_TIER_MULTIPLIER = Decimal("1.5")

SUB_ACTIVE, SUB_SUSPENDED, SUB_CANCELLED = 10, 20, 30
TENANT_ACTIVE, TENANT_SUSPENDED = 10, 20
INVOICE_ISSUED, INVOICE_OVERDUE = 20, 40
DUNNING_SCHEDULED = 10
NOTIFY_SUSPENSION = 3
SUSPEND_AFTER_DAYS = 14


def md5_uuid(text):
    """`PKG_OW_UTIL.f_md5_uuid`. Keys derived this way are how the estate makes its writes
    idempotent, so the digest has to stay bit-identical to Oracle's STANDARD_HASH(MD5)."""
    h = hashlib.md5(text.encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def dt2str(value):
    """`PKG_OW_UTIL.f_dt2str`: the DD-MON-YY string form dates travel in."""
    return None if value is None else value.strftime("%d-%b-%y").upper()


def str2dt(text):
    """`PKG_OW_UTIL.f_str2dt`. The original returns NULL for anything unparseable and tells
    nobody; the migration quarantines those values instead, so this is only ever called on
    strings that already parsed during the load."""
    if text is None:
        return None
    try:
        # the estate's string dates carry no zone; the session runs UTC (tolerances v1)
        return dt.datetime.strptime(text.strip(), "%d-%b-%y").replace(tzinfo=dt.UTC).date()
    except ValueError:
        return None


def rnd(value, places=2):
    """Oracle ROUND: half away from zero, unlike Python's banker's rounding."""
    if value is None:
        return None
    q = Decimal(1).scaleb(-places)
    return Decimal(value).quantize(q, rounding=ROUND_HALF_UP)


def _least(*values):
    """Oracle LEAST/GREATEST propagate NULL; Postgres ignores it. The estate's own code
    already collapses the NULL operand where the two dialects disagreed, so the guard here
    mirrors what the PL/SQL does rather than what SQL would do."""
    return None if any(v is None for v in values) else min(values)


def _greatest(*values):
    return None if any(v is None for v in values) else max(values)


def _as_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    return value


def _ymd(value):
    """The estate compares dates by their YYYYMMDD text, the mainframe way. Preserved because
    it is what decides period membership for a timestamped usage event."""
    return _as_date(value).strftime("%Y%m%d")


def _covers(sub, start, end):
    starts = _as_date(sub["starts_on"])
    ends = _as_date(sub.get("ends_on"))
    return starts <= end and (ends is None or ends >= start)


def _latest(subs):
    return max(subs, key=lambda s: _as_date(s["starts_on"]), default=None)


# --- PKG_PLANS ------------------------------------------------------------------------


def list_plans(store):
    """`PKG_PLANS.fn_list_plans`."""
    store.log("PLANS", "fn_list_plans")
    plans = [p for p in store.plans() if p.get("legacy", {}).get("active_yn", "N") == "Y"]
    plans.sort(key=lambda p: (Decimal(str(p["monthly_fee"])), p["code"]))
    return [
        {
            "plan_id": p["_id"],
            "code": p["code"],
            "tier": store.code_desc("PLAN_TIER", p["tier_cd"]),
            "monthly_fee": Decimal(str(p["monthly_fee"])),
            "included_units": p["included_units"],
            "overage_rate": Decimal(str(p["overage_rate"])),
        }
        for p in plans
    ]


def entitlement(store, tenant_id, on):
    """`PKG_PLANS.fn_entitlement`: the covering subscription with the latest start."""
    on = _as_date(on)
    tenant = store.tenant(tenant_id)
    if tenant is None:
        return []
    covering = [s for s in store.subscriptions(tenant_id) if _covers(s, on, on)]
    sub = _latest(covering)
    if sub is None:
        return []
    plan = store.plan(sub.get("plan_id")) or {}
    return [
        {
            "tenant_id": tenant["_id"],
            "plan_code": plan.get("code"),
            "tier": store.code_desc("PLAN_TIER", plan["tier_cd"]) if plan else "UNKNOWN",
            "monthly_fee": Decimal(str(plan["monthly_fee"])) if plan else None,
            "included_units": plan.get("included_units"),
            "subscription_status": store.code_desc("SUB_STATUS", sub["status_cd"]),
            "effective_on": max(_as_date(sub["starts_on"]), on),
        }
    ]


def change_plan(store, tenant_id, plan_id, effective_on):
    """`PKG_PLANS.sp_change_plan`. The row-by-row close-out loop collapses to one pass, and
    TRG_SUB_NO_UNCANCEL's rule -- a cancelled subscription never leaves the cancelled state
    -- moves into `Store.update_subscription`, which is the only writer of `status_cd`."""
    effective_on = _as_date(effective_on)
    store.log(
        "PLANS",
        f"sp_change_plan tenant={tenant_id} plan={plan_id} eff={effective_on.isoformat()}",
    )
    with store.unit_of_work():
        for sub in store.subscriptions(tenant_id):
            if sub.get("ends_on") is None and _as_date(sub["starts_on"]) < effective_on:
                store.update_subscription(
                    sub["_id"],
                    {
                        "ends_on": effective_on - dt.timedelta(days=1),
                        "status_cd": SUB_CANCELLED
                        if sub["status_cd"] == SUB_CANCELLED
                        else SUB_ACTIVE,
                    },
                )
        store.insert_subscription(
            {
                "_id": md5_uuid(f"{tenant_id}{plan_id}{effective_on.isoformat()}"),
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "starts_on": effective_on,
                "status_cd": SUB_ACTIVE,
            }
        )


# --- PKG_RATING -----------------------------------------------------------------------


@dataclass
class Rating:
    """What PKG_RATING used to leave in package globals between two calls."""

    tenant_id: str
    period_start: dt.date
    period_end: dt.date
    used_units: int
    quota_units: int | None
    rollover_units: int | None
    billable_units: int | None
    first_tier_units: int | None
    second_tier_units: int | None
    overage_amount: Decimal | None
    subscription_id: str | None


def compute_rating(store, tenant_id, period_start, period_end):
    """`PKG_RATING.compute_rating`."""
    period_start, period_end = _as_date(period_start), _as_date(period_end)
    sub = _latest([s for s in store.subscriptions(tenant_id) if _covers(s, period_start, period_end)])
    plan = store.plan(sub.get("plan_id")) if sub else None
    included = plan["included_units"] if plan else None
    rate = Decimal(str(plan["overage_rate"])) if plan else None

    used = sum(
        e.get("units") or 0
        for e in store.usage_events(tenant_id)
        if _ymd(period_start) <= _ymd(e["occurred_at"]) <= _ymd(period_end)
    )

    prior = sum(
        r.get("rollover_units") or 0
        for period in store.rating_periods(tenant_id)
        for r in period.get("results", [])
        if _months_before(_as_date(period["period_start"]), period_start, 3)
    )
    prior = _least(2 * included, prior) if included is not None else prior

    quota = included
    rollover = _least(prior, included * 2) if included is not None else prior
    billable = 0 if included is None else max(used - rollover - included, 0)
    first_tier = min(billable, TIER_BREAK)
    second_tier = max(billable - TIER_BREAK, 0)
    overage = (
        None
        if rate is None
        else rnd(first_tier * rate + second_tier * rate * SECOND_TIER_MULTIPLIER)
    )

    suspended_on = _as_date(sub.get("suspended_on")) if sub else None
    if (
        sub
        and sub["status_cd"] == SUB_SUSPENDED
        and suspended_on is not None
        and period_start <= suspended_on <= period_end
    ):
        factor = Decimal((period_end - suspended_on).days + 1) / Decimal(
            (period_end - period_start).days + 1
        )
        billable = int(rnd(billable * factor, 0))
        overage = rnd(overage * factor) if overage is not None else None

    store.log("RATING", f"compute tenant={tenant_id} used={used} billable={billable}")
    return Rating(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        used_units=used,
        quota_units=quota,
        rollover_units=rollover,
        billable_units=billable,
        first_tier_units=first_tier,
        second_tier_units=second_tier,
        overage_amount=overage,
        subscription_id=sub["_id"] if sub else None,
    )


def _months_before(period_start, reference, months):
    """ADD_MONTHS(reference, -months) <= period_start < reference."""
    year, month = divmod(reference.month - 1 - months, 12)
    floor = reference.replace(year=reference.year + year, month=month + 1)
    return floor <= period_start < reference


def usage_rating(store, tenant_id, period_start, period_end):
    """`PKG_RATING.fn_usage_rating`."""
    r = compute_rating(store, tenant_id, period_start, period_end)
    return [
        {
            "tenant_id": r.tenant_id,
            "period_start": r.period_start,
            "period_end": r.period_end,
            "used_units": r.used_units,
            "quota_units": r.quota_units,
            "rollover_units": r.rollover_units,
            "billable_units": r.billable_units,
            "first_tier_units": r.first_tier_units,
            "second_tier_units": r.second_tier_units,
            "overage_amount": r.overage_amount,
        }
    ]


def usage_summary(store, tenant_id, period_start, period_end):
    """`PKG_RATING.fn_usage_summary`."""
    period_start, period_end = _as_date(period_start), _as_date(period_end)
    totals = {}
    for event in store.usage_events(tenant_id):
        if not _ymd(period_start) <= _ymd(event["occurred_at"]) <= _ymd(period_end):
            continue
        kind = store.code_desc("USAGE_KIND", event["kind_cd"])
        count, units = totals.get(kind, (0, 0))
        totals[kind] = (count + 1, units + (event.get("units") or 0))
    return [
        {"kind": kind, "event_count": count, "units": units}
        for kind, (count, units) in sorted(totals.items())
    ]


def finalize_rating(store, tenant_id, period_start, period_end):
    """`PKG_RATING.sp_finalize_rating`. The INSERT-then-catch-DUP_VAL_ON_INDEX upsert becomes
    a real upsert; the rating result, one row per period in Oracle, is embedded in its period
    because it is never read without it."""
    period_start, period_end = _as_date(period_start), _as_date(period_end)
    period_id = md5_uuid(f"{tenant_id}{period_start.isoformat()}")
    with store.unit_of_work():
        store.upsert_rating_period(period_id, tenant_id, period_start, period_end)
        r = compute_rating(store, tenant_id, period_start, period_end)
        store.upsert_rating_result(
            period_id,
            {
                "result_id": md5_uuid(period_id),
                "subscription_id": r.subscription_id,
                "used_units": r.used_units,
                "quota_units": r.quota_units,
                # Not the computed rollover: the original writes the unused quota here.
                "rollover_units": _greatest((r.quota_units or 0) - r.used_units, 0),
                "billable_units": r.billable_units,
                "overage_amount": r.overage_amount,
                "created_at": period_end,
            },
        )
    store.log("RATING", f"finalized period={period_id}")
    return period_id


# --- PKG_INVOICING --------------------------------------------------------------------


@dataclass
class Preview:
    plan_code: str | None
    plan_fee: Decimal | None
    overage: Decimal | None
    tax: Decimal | None
    credit: Decimal


def compute_preview(store, tenant_id, period_start, period_end):
    """`PKG_INVOICING.compute_preview`."""
    period_start, period_end = _as_date(period_start), _as_date(period_end)
    plan_code = plan_fee = None
    sub = _latest([s for s in store.subscriptions(tenant_id) if _covers(s, period_start, period_end)])
    plan = store.plan(sub.get("plan_id")) if sub else None
    if plan:
        plan_code, plan_fee = plan["code"], Decimal(str(plan["monthly_fee"]))

    overage = compute_rating(store, tenant_id, period_start, period_end).overage_amount
    credit = sum(
        (Decimal(str(c["remaining_amount"])) for c in store.credit_notes(tenant_id)
         if Decimal(str(c["remaining_amount"])) > 0),
        Decimal(0),
    )
    tenant = store.tenant(tenant_id)
    exempt = bool(tenant and tenant.get("tax_exempt"))
    tax = (
        Decimal(0)
        if exempt
        else (None if plan_fee is None or overage is None else (plan_fee + overage) * TAX_RATE)
    )
    return Preview(plan_code, plan_fee, overage, tax, credit)


def invoice_preview(store, tenant_id, period_start, period_end):
    """`PKG_INVOICING.fn_invoice_preview`: five lines, tax split in half across two of them."""
    p = compute_preview(store, tenant_id, period_start, period_end)
    cap = None
    if p.plan_fee is not None and p.overage is not None and p.tax is not None:
        cap = rnd(p.plan_fee + p.overage + p.tax)
    credit_applied = _least(p.credit, cap) if cap is not None else p.credit
    half_tax = None if p.tax is None else p.tax / 2
    return [
        _line(1, "plan", p.plan_code, rnd(p.plan_fee), 0, rnd(p.plan_fee)),
        _line(2, "usage", "usage overage", rnd(p.overage), 0, rnd(p.overage)),
        _line(3, "tax", "regional tax", half_tax, 0, half_tax),
        _line(4, "tax", "local tax", half_tax, 0, half_tax),
        _line(5, "credit", "credit notes", Decimal(0), credit_applied, -credit_applied),
    ]


def _line(line_no, line_type, description, amount, credit_applied, total):
    return {
        "line_no": line_no,
        "line_type": line_type,
        "description": description,
        "amount": amount,
        "tax_amount": Decimal(0),
        "credit_applied": credit_applied,
        "total": total,
    }


def invoice_lines(store, invoice_id):
    """`PKG_INVOICING.fn_invoice_lines`. The join to INVOICE_LINES is gone: the lines are an
    array inside their invoice."""
    invoice = store.invoice(invoice_id)
    lines = sorted(invoice.get("lines", []), key=lambda line: line["line_no"]) if invoice else []
    return [
        {
            "line_no": line["line_no"],
            "line_type": line["line_type"],
            "description": line.get("description"),
            "amount": Decimal(str(line["amount"])),
        }
        for line in lines
    ]


def issue_invoice(store, tenant_id, period_start, period_end):
    """`PKG_INVOICING.sp_issue_invoice`. One transaction, as the procedure was: the rating
    period, the invoice, its lines, its totals and the credit burn-down commit together or
    not at all -- a half-issued invoice whose credits were already spent would bill a
    different total on the retry."""
    period_start, period_end = _as_date(period_start), _as_date(period_end)
    period_id = md5_uuid(f"{tenant_id}{period_start.isoformat()}")
    invoice_id = md5_uuid(f"{period_id}invoice")

    with store.unit_of_work():
        finalize_rating(store, tenant_id, period_start, period_end)
        store.upsert_invoice(invoice_id, tenant_id, period_id, period_end, INVOICE_ISSUED)

        subtotal = tax = Decimal(0)
        credit = Decimal(0)
        lines = []
        for line in invoice_preview(store, tenant_id, period_start, period_end):
            amount = line["total"] if line["line_type"] == "credit" else line["amount"]
            lines.append(
                {
                    "line_id": md5_uuid(f"{invoice_id}{line['line_no']}"),
                    "line_no": line["line_no"],
                    "line_type": line["line_type"],
                    "description": line["description"],
                    "amount": amount,
                }
            )
            if line["line_type"] in ("plan", "usage"):
                subtotal += rnd(line["amount"]) or Decimal(0)
            elif line["line_type"] == "tax":
                tax += rnd(line["amount"]) or Decimal(0)
            elif line["line_type"] == "credit":
                credit = line["credit_applied"]
        store.set_invoice_lines(invoice_id, lines)

        total = rnd(subtotal + tax - credit)
        store.update_invoice_totals(invoice_id, rnd(subtotal), rnd(tax), total)

        # Oldest credit note first, decrementing the same running counter the original does:
        # the second note is reduced by the *undiminished* balance, not by what is left.
        for note in sorted(
            (c for c in store.credit_notes(tenant_id) if Decimal(str(c["remaining_amount"])) > 0),
            key=lambda c: (_as_date(c["issued_on"]), c["_id"]),
        ):
            if credit <= 0:
                break
            remaining = Decimal(str(note["remaining_amount"]))
            store.update_credit_note(note["_id"], max(remaining - credit, Decimal(0)))
            credit = max(credit - remaining, Decimal(0))

    store.log("INVOICING", f"issued invoice={invoice_id} total={total or 0}")
    return invoice_id


# --- PKG_DUNNING ----------------------------------------------------------------------


def overdue_accounts(store, as_of):
    """`PKG_DUNNING.fn_overdue_accounts`."""
    as_of = _as_date(as_of)
    overdue = [
        invoice
        for invoice in store.invoices_by_status(INVOICE_OVERDUE)
        if _ymd(invoice["issued_at"]) < _ymd(as_of)
    ]
    overdue.sort(key=lambda i: (_as_date(i["issued_at"]), i["_id"]))
    rows = []
    for invoice in overdue:
        tenant = store.tenant(invoice["tenant_id"])
        rows.append(
            {
                "tenant_id": invoice["tenant_id"],
                "invoice_id": invoice["_id"],
                "total": Decimal(str(invoice["total"])),
                "days_overdue": (as_of - _as_date(invoice["issued_at"])).days,
                "tenant_status": store.code_desc("TENANT_STATUS", tenant["status_cd"])
                if tenant
                else "UNKNOWN",
            }
        )
    return rows


def next_business_day(day):
    """The weekend shift the original does with TO_CHAR(...,'DY') and DECODE."""
    return day + dt.timedelta(days={5: 2, 6: 1}.get(day.weekday(), 0))


def schedule_dunning(store, as_of):
    """`PKG_DUNNING.sp_schedule_dunning`. `WHEN OTHERS THEN NULL` around the INSERT was doing
    the work of ON CONFLICT DO NOTHING; here the unique (invoice_id, attempt_no) index says
    so explicitly and only that conflict is ignored."""
    as_of = _as_date(as_of)
    scheduled = 0
    with store.unit_of_work():
        for invoice in sorted(
            store.invoices_by_status(INVOICE_OVERDUE),
            key=lambda i: (_as_date(i["issued_at"]), i["_id"]),
        ):
            attempts = store.dunning_attempts(invoice["_id"])
            attempt_no = max((a["attempt_no"] for a in attempts), default=0) + 1
            if store.insert_dunning_attempt(
                {
                    "_id": md5_uuid(f"{invoice['_id']}{attempt_no}"),
                    "tenant_id": invoice["tenant_id"],
                    "invoice_id": invoice["_id"],
                    "attempt_no": attempt_no,
                    "scheduled_for": next_business_day(as_of),
                    "status_cd": DUNNING_SCHEDULED,
                }
            ):
                scheduled += 1
    store.log("DUNNING", f"scheduled {scheduled} attempts as of {dt2str(as_of)}")
    return scheduled


def nightly_dunning(store, as_of):
    """The replacement for the JOB_NIGHTLY_DUNNING scheduler job: the same two calls, in the
    same order, invoked by the application's scheduler instead of DBMS_SCHEDULER."""
    scheduled = schedule_dunning(store, as_of)
    suspend_overdue(store, as_of)
    return scheduled


def suspend_overdue(store, as_of):
    """`PKG_DUNNING.sp_suspend_overdue`."""
    as_of = _as_date(as_of)
    cutoff = as_of - dt.timedelta(days=SUSPEND_AFTER_DAYS)
    tenant_ids = sorted(
        {
            invoice["tenant_id"]
            for invoice in store.invoices_by_status(INVOICE_OVERDUE)
            if _ymd(invoice["issued_at"]) <= _ymd(cutoff)
        }
    )
    with store.unit_of_work():
        for tenant_id in tenant_ids:
            tenant = store.tenant(tenant_id)
            if tenant is None or tenant["status_cd"] != TENANT_ACTIVE:
                continue
            store.update_tenant_status(tenant_id, TENANT_SUSPENDED)
            for sub in store.subscriptions(tenant_id):
                if sub["status_cd"] == SUB_ACTIVE:
                    store.update_subscription(
                        sub["_id"], {"status_cd": SUB_SUSPENDED, "suspended_on": as_of}
                    )
            store.insert_notification_once(
                {
                    "_id": md5_uuid(f"{tenant_id}suspension{as_of.isoformat()}"),
                    "tenant_id": tenant_id,
                    "kind_cd": NOTIFY_SUSPENSION,
                    "sent_at": as_of,
                }
            )
        store.log("DUNNING", f"suspended tenant={tenant_id}")
