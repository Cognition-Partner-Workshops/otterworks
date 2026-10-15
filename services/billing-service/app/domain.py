from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from hashlib import md5
from typing import Protocol
from uuid import UUID


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
    # sp_change_plan: md5(p_tenant_id::text || p_plan_id::text || p_effective_on::text)::uuid
    created_id = UUID(md5(f"{tenant_id}{plan_id}{effective_on.isoformat()}".encode()).hexdigest())
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


FIRST_TIER_UNITS = 101
SECOND_TIER_MULTIPLIER = Decimal("1.5")
ROLLOVER_WINDOW_MONTHS = 3
CENTS = Decimal("0.01")


@dataclass(frozen=True)
class UsageRatingRow:
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
    subscription_id: UUID


@dataclass(frozen=True)
class UsageSummaryRow:
    kind: str
    event_count: int
    units: int


@dataclass(frozen=True)
class RatingResultRow:
    period_id: UUID
    result_id: UUID
    subscription_id: UUID
    used_units: int
    quota_units: int
    rollover_units: int
    billable_units: int
    overage_amount: Decimal


class RatingRepository(Protocol):
    def list_plans(self) -> list[PlanRow]: ...

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...

    def sum_usage_units(self, tenant_id: UUID, period_start: date, period_end: date) -> int: ...

    def usage_by_kind(
        self, tenant_id: UUID, period_start: date, period_end: date
    ) -> list[UsageSummaryRow]: ...

    def sum_prior_rollover_units(
        self, tenant_id: UUID, window_start: date, period_start: date
    ) -> int: ...

    def upsert_rating_period(
        self, tenant_id: UUID, period_id: UUID, period_start: date, period_end: date
    ) -> UUID: ...

    def upsert_rating_result(self, result: RatingResultRow, created_at: date) -> None: ...


class NoSubscriptionError(LookupError):
    """No subscription of the tenant overlaps the rating period."""


def _round_half_up(value: Decimal, exponent: Decimal = Decimal("1")) -> Decimal:
    # PostgreSQL round(numeric) rounds half away from zero, like ROUND_HALF_UP.
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def months_before(day: date, months: int) -> date:
    """PostgreSQL `date - interval 'N months'`: same day of month, clamped to month end."""
    month_index = day.year * 12 + (day.month - 1) - months
    year, month = divmod(month_index, 12)
    month += 1
    last_day = (date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last_day))


def covering_subscription(
    subscriptions: list[SubscriptionRow], period_start: date, period_end: date
) -> SubscriptionRow | None:
    """rating.sql: the latest-starting subscription overlapping the period."""
    eligible = [
        row
        for row in subscriptions
        if row.starts_on <= period_end and (row.ends_on is None or row.ends_on >= period_start)
    ]
    return max(eligible, key=lambda row: row.starts_on, default=None)


def usage_rating(
    repository: RatingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> UsageRatingRow:
    subscription = covering_subscription(
        repository.list_subscriptions(tenant_id), period_start, period_end
    )
    if subscription is None:
        raise NoSubscriptionError(f"tenant {tenant_id} has no subscription in the period")
    plan = next(item for item in repository.list_plans() if item.plan_id == subscription.plan_id)
    used = repository.sum_usage_units(tenant_id, period_start, period_end)
    prior = repository.sum_prior_rollover_units(
        tenant_id, months_before(period_start, ROLLOVER_WINDOW_MONTHS), period_start
    )
    rollover = min(prior, 2 * plan.included_units)
    billable = max(used - rollover - plan.included_units, 0)
    first = min(billable, FIRST_TIER_UNITS)
    second = max(billable - FIRST_TIER_UNITS, 0)
    amount = _round_half_up(
        first * plan.overage_rate + second * plan.overage_rate * SECOND_TIER_MULTIPLIER, CENTS
    )
    if (
        subscription.status == "suspended"
        and subscription.suspended_on is not None
        and period_start <= subscription.suspended_on <= period_end
    ):
        remaining = Decimal((period_end - subscription.suspended_on).days + 1) / Decimal(
            (period_end - period_start).days + 1
        )
        billable = int(_round_half_up(billable * remaining))
        amount = _round_half_up(amount * remaining, CENTS)
    return UsageRatingRow(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        used_units=used,
        quota_units=plan.included_units,
        rollover_units=rollover,
        billable_units=billable,
        first_tier_units=first,
        second_tier_units=second,
        overage_amount=amount,
        subscription_id=subscription.subscription_id,
    )


def usage_summary(
    repository: RatingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> list[UsageSummaryRow]:
    return sorted(
        repository.usage_by_kind(tenant_id, period_start, period_end), key=lambda row: row.kind
    )


def legacy_uuid(*parts: object) -> UUID:
    """PostgreSQL md5(a::text || b::text)::uuid."""
    return UUID(md5("".join(str(part) for part in parts).encode()).hexdigest())


def finalize_rating(
    repository: RatingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> RatingResultRow:
    """sp_finalize_rating: upsert the period keyed by (tenant, period_start), rate it, and
    upsert its single result. Running it twice for the same period yields the same documents."""
    period_id = repository.upsert_rating_period(
        tenant_id, legacy_uuid(tenant_id, period_start.isoformat()), period_start, period_end
    )
    rating = usage_rating(repository, tenant_id, period_start, period_end)
    result = RatingResultRow(
        period_id=period_id,
        result_id=legacy_uuid(period_id),
        subscription_id=rating.subscription_id,
        used_units=rating.used_units,
        quota_units=rating.quota_units,
        rollover_units=max(rating.quota_units - rating.used_units, 0),
        billable_units=rating.billable_units,
        overage_amount=rating.overage_amount,
    )
    repository.upsert_rating_result(result, period_end)
    return result
