"""Temporary copy of the legacy rating logic used by invoicing.

This mirrors only the parts of billing.fn_usage_rating and billing.sp_finalize_rating
that billing.fn_invoice_preview and billing.sp_issue_invoice exercise. It is pending
the rating extraction and should be replaced by the rating module's implementation
when that lands.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.domain import PlanRow, SubscriptionRow

FIRST_TIER_UNITS = 101
SECOND_TIER_MULTIPLIER = Decimal("1.5")
ROLLOVER_LOOKBACK_MONTHS = 3


@dataclass(frozen=True)
class UsageRating:
    used_units: int
    quota_units: int
    rollover_units: int
    billable_units: int
    first_tier_units: int
    second_tier_units: int
    overage_amount: Decimal


def _months_before(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def select_subscription(
    subscriptions: list[SubscriptionRow], period_start: date, period_end: date
) -> SubscriptionRow | None:
    overlapping = [
        item
        for item in subscriptions
        if item.starts_on <= period_end and (item.ends_on is None or item.ends_on >= period_start)
    ]
    return max(overlapping, key=lambda item: item.starts_on, default=None)


def prior_rollover(plan: PlanRow, history: list[tuple[date, int]], period_start: date) -> int:
    lookback = _months_before(period_start, ROLLOVER_LOOKBACK_MONTHS)
    carried = sum(units for started, units in history if lookback <= started < period_start)
    return min(2 * plan.included_units, carried)


def rate_usage(
    plan: PlanRow,
    subscription: SubscriptionRow,
    used_units: int,
    prior_rollover_units: int,
    period_start: date,
    period_end: date,
) -> UsageRating:
    rollover = min(prior_rollover_units, plan.included_units * 2)
    billable = max(used_units - rollover - plan.included_units, 0)
    first = min(billable, FIRST_TIER_UNITS)
    second = max(billable - FIRST_TIER_UNITS, 0)
    amount = (
        first * plan.overage_rate + second * plan.overage_rate * SECOND_TIER_MULTIPLIER
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if (
        subscription.status == "suspended"
        and subscription.suspended_on is not None
        and period_start <= subscription.suspended_on <= period_end
    ):
        ratio = Decimal((period_end - subscription.suspended_on).days + 1) / Decimal(
            (period_end - period_start).days + 1
        )
        billable = int((billable * ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        amount = (amount * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return UsageRating(
        used_units=used_units,
        quota_units=plan.included_units,
        rollover_units=rollover,
        billable_units=billable,
        first_tier_units=first,
        second_tier_units=second,
        overage_amount=amount,
    )


def finalized_rollover(rating: UsageRating) -> int:
    return max(rating.quota_units - rating.used_units, 0)
