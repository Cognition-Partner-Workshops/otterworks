from __future__ import annotations

import calendar
import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Protocol
from uuid import UUID, uuid5

PLAN_CHANGE_NAMESPACE = UUID("d8e9df63-6e46-4d6a-b9c2-2ef6e99cb5ee")
FIRST_TIER_UNITS = 101
SECOND_TIER_MULTIPLIER = Decimal("1.5")
ROLLOVER_LOOKBACK_MONTHS = 3
ROLLOVER_CAP_MULTIPLIER = 2
CENTS = Decimal("0.01")


@dataclass(frozen=True)
class PlanRow:
    plan_id: UUID
    code: str
    tier: str
    monthly_fee: Decimal
    included_units: int
    overage_rate: Decimal
    active: bool


@dataclass(frozen=True)
class SubscriptionRow:
    subscription_id: UUID
    tenant_id: UUID
    plan_id: UUID
    starts_on: date
    ends_on: date | None
    status: str
    suspended_on: date | None


@dataclass(frozen=True)
class EntitlementRow:
    tenant_id: UUID
    plan_code: str
    tier: str
    monthly_fee: Decimal
    included_units: int
    subscription_status: str
    ends_on: date | None
    starts_on: date


class PlansRepository(Protocol):
    def list_plans(self) -> list[PlanRow]: ...

    def find_entitlements(self, tenant_id: UUID) -> list[EntitlementRow]: ...

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...

    def update_subscription(self, subscription_id: UUID, ends_on: date, status: str) -> None: ...

    def insert_subscription(
        self,
        subscription_id: UUID,
        tenant_id: UUID,
        plan_id: UUID,
        starts_on: date,
        status: str,
    ) -> None: ...


def catalog(plans: list[PlanRow]) -> list[PlanRow]:
    return sorted(
        (plan for plan in plans if plan.active),
        key=lambda plan: (plan.monthly_fee, plan.code),
    )


def entitlement(rows: list[EntitlementRow], tenant_id: UUID, on: date) -> EntitlementRow | None:
    eligible = [
        row
        for row in rows
        if row.tenant_id == tenant_id
        and row.starts_on <= on
        and (row.ends_on is None or row.ends_on >= on)
    ]
    return max(eligible, key=lambda row: row.starts_on, default=None)


def change_plan(
    repository: PlansRepository,
    tenant_id: UUID,
    plan_id: UUID,
    effective_on: date,
) -> tuple[list[SubscriptionRow], SubscriptionRow]:
    subscriptions = repository.list_subscriptions(tenant_id)
    for subscription in subscriptions:
        if subscription.ends_on is None and subscription.starts_on < effective_on:
            next_status = (
                subscription.status if subscription.status == "cancelled" else "active"
            )
            repository.update_subscription(
                subscription.subscription_id,
                effective_on - timedelta(days=1),
                next_status,
            )
    created_id = uuid5(PLAN_CHANGE_NAMESPACE, f"{tenant_id}{plan_id}{effective_on.isoformat()}")
    repository.insert_subscription(
        created_id,
        tenant_id,
        plan_id,
        effective_on,
        "active",
    )
    subscriptions = sorted(
        repository.list_subscriptions(tenant_id), key=lambda item: item.starts_on
    )
    created = next(item for item in subscriptions if item.subscription_id == created_id)
    return subscriptions, created


@dataclass(frozen=True)
class UsageEventRow:
    tenant_id: UUID
    occurred_on: date
    units: int
    kind: str


@dataclass(frozen=True)
class PriorRatingRow:
    period_start: date
    rollover_units: int


@dataclass(frozen=True)
class Rating:
    tenant_id: UUID
    period_start: date
    period_end: date
    used_units: int
    quota_units: int | None
    rollover_units: int
    billable_units: int
    first_tier_units: int
    second_tier_units: int
    overage_amount: Decimal | None


@dataclass(frozen=True)
class UsageSummaryRow:
    kind: str
    event_count: int
    units: int


@dataclass(frozen=True)
class RatingResultRow:
    used_units: int
    quota_units: int
    rollover_units: int
    billable_units: int
    overage_amount: Decimal


class NoRatingSubscriptionError(Exception):
    pass


class RatingRepository(Protocol):
    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...

    def find_plan(self, plan_id: UUID) -> PlanRow | None: ...

    def list_usage_events(self, tenant_id: UUID) -> list[UsageEventRow]: ...

    def list_prior_ratings(self, tenant_id: UUID) -> list[PriorRatingRow]: ...

    def upsert_rating_period(
        self, period_id: UUID, tenant_id: UUID, period_start: date, period_end: date
    ) -> None: ...

    def upsert_rating_result(
        self,
        result_id: UUID,
        period_id: UUID,
        subscription_id: UUID,
        result: RatingResultRow,
        created_on: date,
    ) -> None: ...

    def find_rating_results(self, tenant_id: UUID, period_start: date) -> list[RatingResultRow]: ...


def _round_half_up(value: Decimal, exponent: Decimal) -> Decimal:
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def _minus_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _numeric_weight(value: int) -> tuple[int, int]:
    weight = 0
    while value >= 10000:
        value //= 10000
        weight += 1
    return weight, value


def pg_numeric_divide(numerator: int, denominator: int) -> Decimal:
    """Positive integer division with Postgres numeric result scale and half-up rounding."""
    if numerator == 0:
        return Decimal(0)
    numerator_weight, numerator_first = _numeric_weight(numerator)
    denominator_weight, denominator_first = _numeric_weight(denominator)
    quotient_weight = numerator_weight - denominator_weight
    if numerator_first <= denominator_first:
        quotient_weight -= 1
    scale = min(max(16 - quotient_weight * 4, 0), 1000)
    scaled = (2 * numerator * 10**scale + denominator) // (2 * denominator)
    return Decimal(scaled).scaleb(-scale)


def rating_subscription(
    subscriptions: list[SubscriptionRow], period_start: date, period_end: date
) -> SubscriptionRow | None:
    overlapping = [
        item
        for item in subscriptions
        if item.starts_on <= period_end and (item.ends_on is None or item.ends_on >= period_start)
    ]
    return max(overlapping, key=lambda item: item.starts_on, default=None)


def period_usage(
    events: list[UsageEventRow], period_start: date, period_end: date
) -> list[UsageEventRow]:
    return [event for event in events if period_start <= event.occurred_on <= period_end]


def used_units(events: list[UsageEventRow], period_start: date, period_end: date) -> int:
    return sum(event.units for event in period_usage(events, period_start, period_end))


def rollover_units(
    prior: list[PriorRatingRow], period_start: date, included_units: int | None
) -> int:
    window_start = _minus_months(period_start, ROLLOVER_LOOKBACK_MONTHS)
    total = sum(
        row.rollover_units for row in prior if window_start <= row.period_start < period_start
    )
    if included_units is None:
        return total
    # rating.sql applies this cap at lines 48 and 56; the second pass is a no-op.
    return min(total, ROLLOVER_CAP_MULTIPLIER * included_units)


def billable_units(used: int, rollover: int, included_units: int) -> int:
    return max(used - rollover - included_units, 0)


def tier_units(billable: int) -> tuple[int, int]:
    return min(billable, FIRST_TIER_UNITS), max(billable - FIRST_TIER_UNITS, 0)


def overage_amount(first_tier: int, second_tier: int, overage_rate: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 100
        amount = (
            first_tier * overage_rate + second_tier * overage_rate * SECOND_TIER_MULTIPLIER
        )
        return _round_half_up(amount, CENTS)


def suspension_fraction(
    subscription: SubscriptionRow, period_start: date, period_end: date
) -> Decimal | None:
    if (
        subscription.status != "suspended"
        or subscription.suspended_on is None
        or not period_start <= subscription.suspended_on <= period_end
    ):
        return None
    return pg_numeric_divide(
        (period_end - subscription.suspended_on).days + 1,
        (period_end - period_start).days + 1,
    )


def prorate(billable: int, amount: Decimal, fraction: Decimal) -> tuple[int, Decimal]:
    with localcontext() as context:
        context.prec = 100
        prorated_units = int(_round_half_up(billable * fraction, Decimal(1)))
        prorated_amount = _round_half_up(amount * fraction, CENTS)
    return prorated_units, prorated_amount


def rate_usage(
    tenant_id: UUID,
    period_start: date,
    period_end: date,
    subscription: SubscriptionRow | None,
    plan: PlanRow | None,
    events: list[UsageEventRow],
    prior: list[PriorRatingRow],
) -> Rating:
    used = used_units(events, period_start, period_end)
    if subscription is None or plan is None:
        return Rating(
            tenant_id,
            period_start,
            period_end,
            used,
            None,
            rollover_units(prior, period_start, None),
            0,
            0,
            0,
            None,
        )
    rollover = rollover_units(prior, period_start, plan.included_units)
    billable = billable_units(used, rollover, plan.included_units)
    first_tier, second_tier = tier_units(billable)
    amount = overage_amount(first_tier, second_tier, plan.overage_rate)
    fraction = suspension_fraction(subscription, period_start, period_end)
    if fraction is not None:
        billable, amount = prorate(billable, amount, fraction)
    return Rating(
        tenant_id,
        period_start,
        period_end,
        used,
        plan.included_units,
        rollover,
        billable,
        first_tier,
        second_tier,
        amount,
    )


def usage_rating(
    repository: RatingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> Rating:
    subscription = rating_subscription(
        repository.list_subscriptions(tenant_id), period_start, period_end
    )
    plan = repository.find_plan(subscription.plan_id) if subscription else None
    return rate_usage(
        tenant_id,
        period_start,
        period_end,
        subscription,
        plan,
        repository.list_usage_events(tenant_id),
        repository.list_prior_ratings(tenant_id),
    )


def usage_summary(
    events: list[UsageEventRow], period_start: date, period_end: date
) -> list[UsageSummaryRow]:
    totals: dict[str, tuple[int, int]] = {}
    for event in period_usage(events, period_start, period_end):
        count, units = totals.get(event.kind, (0, 0))
        totals[event.kind] = (count + 1, units + event.units)
    return [UsageSummaryRow(kind, *totals[kind]) for kind in sorted(totals)]


def _md5_uuid(value: str) -> UUID:
    return UUID(hex=hashlib.md5(value.encode(), usedforsecurity=False).hexdigest())


def rating_period_id(tenant_id: UUID, period_start: date) -> UUID:
    return _md5_uuid(f"{tenant_id}{period_start.isoformat()}")


def rating_result_id(period_id: UUID) -> UUID:
    return _md5_uuid(str(period_id))


def finalize_rating(
    repository: RatingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> list[RatingResultRow]:
    subscription = rating_subscription(
        repository.list_subscriptions(tenant_id), period_start, period_end
    )
    if subscription is None:
        raise NoRatingSubscriptionError(tenant_id)
    period_id = rating_period_id(tenant_id, period_start)
    repository.upsert_rating_period(period_id, tenant_id, period_start, period_end)
    rating = usage_rating(repository, tenant_id, period_start, period_end)
    repository.upsert_rating_result(
        rating_result_id(period_id),
        period_id,
        subscription.subscription_id,
        RatingResultRow(
            used_units=rating.used_units,
            quota_units=rating.quota_units,
            rollover_units=max(rating.quota_units - rating.used_units, 0),
            billable_units=rating.billable_units,
            overage_amount=rating.overage_amount,
        ),
        period_end,
    )
    return repository.find_rating_results(tenant_id, period_start)
