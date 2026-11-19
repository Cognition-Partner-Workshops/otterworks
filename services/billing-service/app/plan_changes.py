from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from uuid import UUID, uuid5

from app.domain import change_plan

INVOICE_NAMESPACE = UUID("f59198de-4078-4fa9-bb9c-bf729e42d9f8")


class PlanChangeError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


def billing_cycle(anchor: date, on: date) -> tuple[date, date]:
    def start(month_index):
        year, month = divmod(month_index, 12)
        month += 1
        return date(year, month, min(anchor.day, monthrange(year, month)[1]))

    month = on.year * 12 + on.month - 1
    if start(month) > on:
        month -= 1
    return start(month), start(month + 1)


def upgrade_lines(old: Decimal, new: Decimal, remaining: int, days: int):
    def rounded(value):
        cents = Fraction(value) * remaining * 100 / days
        whole, remainder = divmod(cents.numerator, cents.denominator)
        return Decimal(whole + (remainder * 2 >= cents.denominator)) / 100

    due = rounded(new - old)
    credit = -rounded(old)
    return due, credit, due - credit


def readable(on: date) -> str:
    return f"{on:%b} {on.day}, {on.year}"


def quote_plan_change(repository, tenant_id: UUID, plan_id: UUID, on: date) -> dict:
    plans = {plan.plan_id: plan for plan in repository.list_plans()}
    new = plans.get(plan_id)
    if new is None:
        raise PlanChangeError(404, "Plan not found")
    if not new.active:
        raise PlanChangeError(400, "This plan is no longer available")
    subscriptions = repository.list_subscriptions(tenant_id)
    current = max(
        (s for s in subscriptions if s.starts_on <= on and (s.ends_on is None or s.ends_on >= on)),
        key=lambda s: s.starts_on,
        default=None,
    )
    if current is None:
        raise PlanChangeError(404, "No subscription found for this date")
    if current.status != "active":
        raise PlanChangeError(409, f"Your subscription is {current.status}; contact support")
    old = plans[current.plan_id]
    if old.plan_id == new.plan_id:
        raise PlanChangeError(409, "You're already on this plan")
    if old.monthly_fee == new.monthly_fee:
        raise PlanChangeError(400, "Please choose a plan with a different monthly price")
    start, next_start = billing_cycle(min(s.starts_on for s in subscriptions), on)
    end = next_start - timedelta(days=1)
    remaining, days = (next_start - on).days, (next_start - start).days
    upgrade = new.monthly_fee > old.monthly_fee
    old_name, new_name = old.code.title(), new.code.title()
    lines = []
    due = Decimal("0")
    if upgrade:
        due, credit, charge = upgrade_lines(old.monthly_fee, new.monthly_fee, remaining, days)
        period = f"{readable(on)} – {readable(end)} ({remaining} of {days} days)"
        lines = [
            {
                "description": f"Credit for unused time on {old_name}, {period}",
                "amount": f"{credit:.2f}",
            },
            {
                "description": f"{new_name} plan for the rest of this billing period, {period}",
                "amount": f"{charge:.2f}",
            },
        ]
        summary = (
            f"Your plan changes from {old_name} to {new_name} today, "
            f"{readable(on)}, with a prorated charge of ${due:.2f} "
            "for the rest of this billing period."
        )
    else:
        summary = (
            f"Your plan changes from {old_name} to {new_name} on "
            f"{readable(next_start)}, when your next billing period starts; "
            f"you keep {old_name} until then and won't be charged today."
        )

    def plan_info(plan):
        return {
            "code": plan.code,
            "name": plan.code.title(),
            "monthly_fee": f"{plan.monthly_fee:.2f}",
        }

    return {
        "kind": "upgrade" if upgrade else "downgrade",
        "current_plan": plan_info(old),
        "new_plan": plan_info(new),
        "requested_on": on.isoformat(),
        "effective_on": (on if upgrade else next_start).isoformat(),
        "cycle_start": start.isoformat(),
        "cycle_end": end.isoformat(),
        "days_in_cycle": days,
        "days_remaining": remaining,
        "amount_due": f"{due:.2f}",
        "lines": lines,
        "summary": summary,
    }


def apply_plan_change(repository, tenant_id: UUID, plan_id: UUID, on: date) -> dict:
    repository.lock_tenant(tenant_id)
    invoice_id = uuid5(INVOICE_NAMESPACE, f"{tenant_id}:{plan_id}:{on}")
    if repository.invoice_exists(invoice_id):
        raise PlanChangeError(409, "This plan change has already been requested")
    result = quote_plan_change(repository, tenant_id, plan_id, on)
    subscriptions = repository.list_subscriptions(tenant_id)
    current = max(
        (s for s in subscriptions if s.starts_on <= on and (s.ends_on is None or s.ends_on >= on)),
        key=lambda s: s.starts_on,
    )
    repository.delete_pending_subscriptions(tenant_id, on)
    repository.reopen_subscription(current.subscription_id)
    if result["kind"] == "upgrade" and current.starts_on == on:
        repository.set_subscription_plan(current.subscription_id, plan_id)
    else:
        change_plan(repository, tenant_id, plan_id, date.fromisoformat(result["effective_on"]))
    invoice = None
    if result["kind"] == "upgrade":
        invoice = {
            "id": str(invoice_id),
            "tenant_id": str(tenant_id),
            "issued_on": on.isoformat(),
            "period_start": on.isoformat(),
            "period_end": result["cycle_end"],
            "total": result["amount_due"],
            "summary": result["summary"],
            "lines": result["lines"],
        }
        repository.insert_invoice(invoice)
    result["invoice"] = invoice
    result["subscriptions"] = [
        {
            "plan_id": str(s.plan_id),
            "starts_on": s.starts_on.isoformat(),
            "ends_on": s.ends_on.isoformat() if s.ends_on else None,
            "status": s.status,
        }
        for s in sorted(repository.list_subscriptions(tenant_id), key=lambda s: s.starts_on)
    ]
    return result
