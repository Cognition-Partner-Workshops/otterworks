from __future__ import annotations

import calendar
import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
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


# --- rating ---
FIRST_TIER_UNITS = 101
SECOND_TIER_MULTIPLIER = Decimal("1.5")
ROLLOVER_LOOKBACK_MONTHS = 3
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
    occurred_on: date
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
    quota_units: int
    rollover_units: int
    billable_units: int
    first_tier_units: int
    second_tier_units: int
    overage_amount: Decimal


@dataclass(frozen=True)
class UsageSummaryRow:
    kind: str
    event_count: int
    units: int


@dataclass(frozen=True)
class RatingResultRow:
    result_id: UUID
    period_id: UUID
    subscription_id: UUID
    used_units: int
    quota_units: int
    rollover_units: int
    billable_units: int
    overage_amount: Decimal
    created_at: datetime


class RatingRepository(Protocol):
    def list_rating_subscriptions(self, tenant_id: UUID) -> list[RatingSubscription]: ...

    def list_usage_events(self, tenant_id: UUID) -> list[UsageEvent]: ...

    def list_prior_rollovers(self, tenant_id: UUID) -> list[PriorRollover]: ...

    def upsert_rating_period(
        self,
        period_id: UUID,
        tenant_id: UUID,
        period_start: date,
        period_end: date,
    ) -> None: ...

    def upsert_rating_result(self, row: RatingResultRow) -> None: ...

    def find_rating_results(
        self, tenant_id: UUID, period_start: date
    ) -> list[RatingResultRow]: ...


class RatingSubscriptionNotFound(LookupError):  # noqa: N818
    pass


def select_rating_subscription(
    subscriptions: list[RatingSubscription],
    period_start: date,
    period_end: date,
) -> RatingSubscription | None:
    eligible = [
        subscription
        for subscription in subscriptions
        if subscription.starts_on <= period_end
        and (subscription.ends_on is None or subscription.ends_on >= period_start)
    ]
    return max(eligible, key=lambda item: item.starts_on, default=None)


def used_units(events: list[UsageEvent], start: date, end: date) -> int:
    return sum(
        event.units for event in events if start <= event.occurred_on <= end
    )


def subtract_months(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, month = divmod(month_index, 12)
    last_day = calendar.monthrange(year, month + 1)[1]
    return date(year, month + 1, min(day.day, last_day))


def available_rollover(
    prior: list[PriorRollover],
    period_start: date,
    included_units: int,
) -> int:
    lookback_start = subtract_months(period_start, ROLLOVER_LOOKBACK_MONTHS)
    earned = sum(
        rollover.rollover_units
        for rollover in prior
        if lookback_start <= rollover.period_start < period_start
    )
    return min(ROLLOVER_CAP_MULTIPLIER * included_units, earned)


def round_half_up(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def rate_usage(
    tenant_id: UUID,
    period_start: date,
    period_end: date,
    subscription: RatingSubscription,
    events: list[UsageEvent],
    prior: list[PriorRollover],
) -> Rating:
    used = used_units(events, period_start, period_end)
    rollover = available_rollover(prior, period_start, subscription.included_units)
    billable = max(used - rollover - subscription.included_units, 0)
    first = min(billable, FIRST_TIER_UNITS)
    second = max(billable - FIRST_TIER_UNITS, 0)
    amount = round_half_up(
        first * subscription.overage_rate
        + second * subscription.overage_rate * SECOND_TIER_MULTIPLIER,
        "0.01",
    )
    if (
        subscription.status == "suspended"
        and subscription.suspended_on is not None
        and period_start <= subscription.suspended_on <= period_end
    ):
        factor = Decimal((period_end - subscription.suspended_on).days + 1) / Decimal(
            (period_end - period_start).days + 1
        )
        billable = int(round_half_up(Decimal(billable) * factor, "1"))
        amount = round_half_up(amount * factor, "0.01")
    return Rating(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        used_units=used,
        quota_units=subscription.included_units,
        rollover_units=rollover,
        billable_units=billable,
        first_tier_units=first,
        second_tier_units=second,
        overage_amount=amount,
    )


def usage_summary(
    events: list[UsageEvent], start: date, end: date
) -> list[UsageSummaryRow]:
    grouped: dict[str, list[int]] = {}
    for event in events:
        if start <= event.occurred_on <= end:
            grouped.setdefault(event.kind, [0, 0])
            grouped[event.kind][0] += 1
            grouped[event.kind][1] += event.units
    return [
        UsageSummaryRow(kind=kind, event_count=count, units=units)
        for kind, (count, units) in sorted(grouped.items())
    ]


def rating_period_id(tenant_id: UUID, period_start: date) -> UUID:
    digest = hashlib.md5(f"{tenant_id}{period_start.isoformat()}".encode()).hexdigest()
    return UUID(digest)


def rating_result_id(period_id: UUID) -> UUID:
    return UUID(hashlib.md5(str(period_id).encode()).hexdigest())


def rate_tenant(
    repository: RatingRepository,
    tenant_id: UUID,
    start: date,
    end: date,
) -> Rating:
    subscription = select_rating_subscription(
        repository.list_rating_subscriptions(tenant_id), start, end
    )
    if subscription is None:
        raise RatingSubscriptionNotFound(tenant_id)
    return rate_usage(
        tenant_id,
        start,
        end,
        subscription,
        repository.list_usage_events(tenant_id),
        repository.list_prior_rollovers(tenant_id),
    )


def finalize_rating(
    repository: RatingRepository,
    tenant_id: UUID,
    start: date,
    end: date,
) -> list[RatingResultRow]:
    subscription = select_rating_subscription(
        repository.list_rating_subscriptions(tenant_id), start, end
    )
    if subscription is None:
        raise RatingSubscriptionNotFound(tenant_id)
    period_id = rating_period_id(tenant_id, start)
    repository.upsert_rating_period(period_id, tenant_id, start, end)
    rating = rate_tenant(repository, tenant_id, start, end)
    repository.upsert_rating_result(
        RatingResultRow(
            result_id=rating_result_id(period_id),
            period_id=period_id,
            subscription_id=subscription.subscription_id,
            used_units=rating.used_units,
            quota_units=rating.quota_units,
            rollover_units=max(rating.quota_units - rating.used_units, 0),
            billable_units=rating.billable_units,
            overage_amount=rating.overage_amount,
            created_at=datetime.combine(end, time(), tzinfo=UTC),
        )
    )
    return repository.find_rating_results(tenant_id, start)
