from __future__ import annotations

import calendar
import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Protocol
from uuid import UUID, uuid5

PLAN_CHANGE_NAMESPACE = UUID("d8e9df63-6e46-4d6a-b9c2-2ef6e99cb5ee")


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
            next_status = subscription.status if subscription.status == "cancelled" else "active"
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


FIRST_TIER_LIMIT = 101
SECOND_TIER_MULTIPLIER = Decimal("1.5")
ROLLOVER_WINDOW_MONTHS = 3
ROLLOVER_CAP_MULTIPLIER = 2


@dataclass(frozen=True)
class RatingSubscription:
    subscription_id: UUID
    plan_id: UUID
    starts_on: date
    ends_on: date | None
    status: str
    suspended_on: date | None
    included_units: int
    overage_rate: Decimal


@dataclass(frozen=True)
class UsageEvent:
    occurred_at: datetime
    units: int
    kind: str


@dataclass(frozen=True)
class PriorRollover:
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


class RatingRepository(Protocol):
    def list_rating_subscriptions(self, tenant_id: UUID) -> list[RatingSubscription]: ...

    def list_usage_events(
        self, tenant_id: UUID, period_start: date, period_end: date
    ) -> list[UsageEvent]: ...

    def list_prior_rollovers(self, tenant_id: UUID, before: date) -> list[PriorRollover]: ...

    def upsert_rating_period(
        self, period_id: UUID, tenant_id: UUID, period_start: date, period_end: date
    ) -> None: ...

    def upsert_rating_result(
        self,
        result_id: UUID,
        period_id: UUID,
        subscription_id: UUID | None,
        rating: Rating,
        rollover_units: int,
        created_at: datetime,
    ) -> None: ...

    def find_rating_results(self, tenant_id: UUID, period_start: date) -> list[RatingResultRow]: ...


def legacy_md5_uuid(value: str) -> UUID:
    """Rebuild Postgres ``md5(value)::uuid`` ids; legacy-compatible ids, not security."""
    return UUID(hex=hashlib.md5(value.encode(), usedforsecurity=False).hexdigest())


def round_half_away(value: Decimal, places: int) -> Decimal:
    with localcontext() as context:
        context.prec = 60
        return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _base_10000_weight_and_lead(value: int) -> tuple[int, int]:
    weight = 0
    while value >= 10000:
        value //= 10000
        weight += 1
    return weight, value


def pg_integer_ratio(numerator: int, denominator: int) -> Decimal:
    """Postgres ``int::numeric / int`` for positive integers, at Postgres's result scale."""
    weight1, lead1 = _base_10000_weight_and_lead(numerator)
    weight2, lead2 = _base_10000_weight_and_lead(denominator)
    qweight = weight1 - weight2 - (1 if lead1 <= lead2 else 0)
    scale = min(max(16 - qweight * 4, 0), 1000)
    with localcontext() as context:
        context.prec = scale + 40
        return round_half_away(Decimal(numerator) / Decimal(denominator), scale)


def subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def select_rated_subscription(
    subscriptions: list[RatingSubscription], period_start: date, period_end: date
) -> RatingSubscription | None:
    overlapping = [
        item
        for item in subscriptions
        if item.starts_on <= period_end and (item.ends_on is None or item.ends_on >= period_start)
    ]
    return max(overlapping, key=lambda item: item.starts_on, default=None)


def usage_date(occurred_at: datetime) -> date:
    return occurred_at.astimezone(UTC).date()


def in_period(event: UsageEvent, period_start: date, period_end: date) -> bool:
    return period_start <= usage_date(event.occurred_at) <= period_end


def used_units(events: list[UsageEvent], period_start: date, period_end: date) -> int:
    return sum(event.units for event in events if in_period(event, period_start, period_end))


def rollover_credit(
    prior: list[PriorRollover], period_start: date, included_units: int | None
) -> int:
    window_start = subtract_months(period_start, ROLLOVER_WINDOW_MONTHS)
    total = sum(
        item.rollover_units for item in prior if window_start <= item.period_start < period_start
    )
    if included_units is None:
        return total
    return min(ROLLOVER_CAP_MULTIPLIER * included_units, total)


def billable_units(used: int, rollover: int, included_units: int | None) -> int:
    if included_units is None:
        return 0
    return max(used - rollover - included_units, 0)


def tier_split(billable: int) -> tuple[int, int]:
    return min(billable, FIRST_TIER_LIMIT), max(billable - FIRST_TIER_LIMIT, 0)


def overage_amount(first: int, second: int, rate: Decimal | None) -> Decimal | None:
    if rate is None:
        return None
    return round_half_away(first * rate + second * rate * SECOND_TIER_MULTIPLIER, 2)


def suspension_fraction(
    subscription: RatingSubscription | None, period_start: date, period_end: date
) -> Decimal | None:
    if (
        subscription is None
        or subscription.status != "suspended"
        or subscription.suspended_on is None
        or not period_start <= subscription.suspended_on <= period_end
    ):
        return None
    return pg_integer_ratio(
        (period_end - subscription.suspended_on).days + 1,
        (period_end - period_start).days + 1,
    )


def rate_usage(
    tenant_id: UUID,
    period_start: date,
    period_end: date,
    subscriptions: list[RatingSubscription],
    events: list[UsageEvent],
    prior: list[PriorRollover],
) -> Rating:
    subscription = select_rated_subscription(subscriptions, period_start, period_end)
    included = subscription.included_units if subscription else None
    rate = subscription.overage_rate if subscription else None
    used = used_units(events, period_start, period_end)
    rollover = rollover_credit(prior, period_start, included)
    billable = billable_units(used, rollover, included)
    first, second = tier_split(billable)
    amount = overage_amount(first, second, rate)
    fraction = suspension_fraction(subscription, period_start, period_end)
    if fraction is not None:
        billable = int(round_half_away(billable * fraction, 0))
        if amount is not None:
            amount = round_half_away(amount * fraction, 2)
    return Rating(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        used_units=used,
        quota_units=included,
        rollover_units=rollover,
        billable_units=billable,
        first_tier_units=first,
        second_tier_units=second,
        overage_amount=amount,
    )


def summarize_usage(
    events: list[UsageEvent], period_start: date, period_end: date
) -> list[UsageSummaryRow]:
    totals: dict[str, tuple[int, int]] = {}
    for event in events:
        if in_period(event, period_start, period_end):
            count, units = totals.get(event.kind, (0, 0))
            totals[event.kind] = (count + 1, units + event.units)
    return [
        UsageSummaryRow(kind=kind, event_count=count, units=units)
        for kind, (count, units) in sorted(totals.items())
    ]


def rate_tenant(
    repository: RatingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> Rating:
    return rate_usage(
        tenant_id,
        period_start,
        period_end,
        repository.list_rating_subscriptions(tenant_id),
        repository.list_usage_events(tenant_id, period_start, period_end),
        repository.list_prior_rollovers(tenant_id, period_start),
    )


def rating_period_id(tenant_id: UUID, period_start: date) -> UUID:
    return legacy_md5_uuid(f"{tenant_id}{period_start.isoformat()}")


def finalize_rating(
    repository: RatingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> list[RatingResultRow]:
    period_id = rating_period_id(tenant_id, period_start)
    subscription = select_rated_subscription(
        repository.list_rating_subscriptions(tenant_id), period_start, period_end
    )
    repository.upsert_rating_period(period_id, tenant_id, period_start, period_end)
    rating = rate_tenant(repository, tenant_id, period_start, period_end)
    stored_rollover = (
        max(rating.quota_units - rating.used_units, 0) if rating.quota_units is not None else 0
    )
    repository.upsert_rating_result(
        legacy_md5_uuid(str(period_id)),
        period_id,
        subscription.subscription_id if subscription else None,
        rating,
        stored_rollover,
        datetime.combine(period_end, time.min, tzinfo=UTC),
    )
    return repository.find_rating_results(tenant_id, period_start)
