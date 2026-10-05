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


@dataclass(frozen=True)
class UsageEventRow:
    tenant_id: UUID
    occurred_at: datetime
    units: int
    kind: str


@dataclass(frozen=True)
class PriorRatingRow:
    period_start: date
    rollover_units: int


@dataclass(frozen=True)
class RatingRow:
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
class StoredRatingResult:
    used_units: int
    quota_units: int
    rollover_units: int
    billable_units: int
    overage_amount: Decimal


class NoSubscriptionError(Exception):
    pass


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


class RatingRepository(Protocol):
    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...

    def get_plan(self, plan_id: UUID) -> PlanRow | None: ...

    def list_usage_events(self, tenant_id: UUID) -> list[UsageEventRow]: ...

    def list_prior_ratings(self, tenant_id: UUID) -> list[PriorRatingRow]: ...

    def upsert_rating_period(
        self, period_id: UUID, tenant_id: UUID, start: date, end: date
    ) -> None: ...

    def upsert_rating_result(
        self,
        result_id: UUID,
        period_id: UUID,
        subscription_id: UUID,
        used_units: int,
        quota_units: int | None,
        rollover_units: int,
        billable_units: int,
        overage_amount: Decimal | None,
        created_at: datetime,
    ) -> None: ...

    def get_rating_result(self, tenant_id: UUID, start: date) -> StoredRatingResult: ...


def select_rating_subscription(
    subscriptions: list[SubscriptionRow],
    period_start: date,
    period_end: date,
) -> SubscriptionRow | None:
    eligible = [
        subscription
        for subscription in subscriptions
        if subscription.starts_on <= period_end
        and (subscription.ends_on is None or subscription.ends_on >= period_start)
    ]
    if not eligible:
        return None
    latest_start = max(subscription.starts_on for subscription in eligible)
    return min(
        (subscription for subscription in eligible if subscription.starts_on == latest_start),
        key=lambda subscription: str(subscription.subscription_id),
    )


def _event_date(event: UsageEventRow) -> date:
    return event.occurred_at.astimezone(UTC).date()


def used_units(events: list[UsageEventRow], start: date, end: date) -> int:
    return sum(event.units for event in events if start <= _event_date(event) <= end)


def summarize_usage(
    events: list[UsageEventRow], start: date, end: date
) -> list[UsageSummaryRow]:
    summary: dict[str, tuple[int, int]] = {}
    for event in events:
        if start <= _event_date(event) <= end:
            count, units = summary.get(event.kind, (0, 0))
            summary[event.kind] = count + 1, units + event.units
    return [
        UsageSummaryRow(kind, count, units)
        for kind, (count, units) in sorted(summary.items())
    ]


def _subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def prior_rollover(
    rows: list[PriorRatingRow],
    period_start: date,
    included_units: int | None,
) -> int:
    lower = _subtract_months(period_start, 3)
    total = sum(
        row.rollover_units
        for row in rows
        if lower <= row.period_start < period_start
    )
    return total if included_units is None else min(total, 2 * included_units)


def round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round0(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def rate_usage(
    subscription: SubscriptionRow | None,
    plan: PlanRow | None,
    used: int,
    prior_rollover: int,
    tenant_id: UUID,
    start: date,
    end: date,
) -> RatingRow:
    included = plan.included_units if plan is not None else None
    billable = 0 if included is None else max(used - prior_rollover - included, 0)
    first = min(billable, 101)
    second = max(billable - 101, 0)
    amount = (
        None
        if plan is None
        else round2(
            Decimal(first) * plan.overage_rate
            + Decimal(second) * plan.overage_rate * Decimal("1.5")
        )
    )
    if (
        subscription is not None
        and subscription.status == "suspended"
        and subscription.suspended_on is not None
        and start <= subscription.suspended_on <= end
    ):
        numerator = (end - subscription.suspended_on).days + 1
        denominator = (end - start).days + 1
        factor = Decimal(numerator) / Decimal(denominator)
        billable = round0(Decimal(billable) * Decimal(numerator) / Decimal(denominator))
        amount = None if amount is None else round2(amount * factor)

    return RatingRow(
        tenant_id=tenant_id,
        period_start=start,
        period_end=end,
        used_units=used,
        quota_units=included,
        rollover_units=prior_rollover,
        billable_units=billable,
        first_tier_units=first,
        second_tier_units=second,
        overage_amount=amount,
    )


def rating_period_id(tenant_id: UUID, start: date) -> UUID:
    value = f"{tenant_id}{start.isoformat()}".encode()
    return UUID(hashlib.md5(value).hexdigest())


def rating_result_id(period_id: UUID) -> UUID:
    return UUID(hashlib.md5(str(period_id).encode()).hexdigest())


def rate_period(
    repository: RatingRepository,
    tenant_id: UUID,
    start: date,
    end: date,
) -> RatingRow:
    subscription = select_rating_subscription(
        repository.list_subscriptions(tenant_id), start, end
    )
    plan = repository.get_plan(subscription.plan_id) if subscription is not None else None
    events = repository.list_usage_events(tenant_id)
    prior = repository.list_prior_ratings(tenant_id)
    rollover = prior_rollover(
        prior,
        start,
        plan.included_units if plan is not None else None,
    )
    return rate_usage(
        subscription,
        plan,
        used_units(events, start, end),
        rollover,
        tenant_id,
        start,
        end,
    )


def finalize_rating(
    repository: RatingRepository,
    tenant_id: UUID,
    start: date,
    end: date,
) -> StoredRatingResult:
    subscription = select_rating_subscription(
        repository.list_subscriptions(tenant_id), start, end
    )
    if subscription is None:
        raise NoSubscriptionError(f"no subscription overlaps {start} through {end}")

    period_id = rating_period_id(tenant_id, start)
    repository.upsert_rating_period(period_id, tenant_id, start, end)

    rating = rate_period(repository, tenant_id, start, end)
    repository.upsert_rating_result(
        rating_result_id(period_id),
        period_id,
        subscription.subscription_id,
        rating.used_units,
        rating.quota_units,
        max(rating.quota_units - rating.used_units, 0),
        rating.billable_units,
        rating.overage_amount,
        datetime.combine(end, time.min, tzinfo=UTC),
    )
    return repository.get_rating_result(tenant_id, start)


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
