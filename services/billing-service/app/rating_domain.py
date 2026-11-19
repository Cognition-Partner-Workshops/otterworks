from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, tzinfo
from decimal import ROUND_HALF_UP, Decimal
from hashlib import md5
from typing import Protocol
from uuid import UUID

from app.domain import PlanRow, SubscriptionRow


@dataclass(frozen=True)
class UsageEventRow:
    tenant_id: UUID
    occurred_at: datetime
    units: int
    kind: str


@dataclass(frozen=True)
class PriorRatingRow:
    tenant_id: UUID
    period_start: date
    rollover_units: int


@dataclass(frozen=True)
class UsageRating:
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
class UsageSummary:
    kind: str
    event_count: int
    units: int


@dataclass(frozen=True)
class RatingPeriodRow:
    id: UUID
    tenant_id: UUID
    period_start: date
    period_end: date


@dataclass(frozen=True)
class RatingResultRow:
    id: UUID
    period_id: UUID
    subscription_id: UUID
    used_units: int
    quota_units: int
    rollover_units: int
    billable_units: int
    overage_amount: Decimal
    created_at: datetime


class RatingRepository(Protocol):
    def list_plans(self) -> list[PlanRow]: ...
    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...
    def list_usage_events(self, tenant_id: UUID) -> list[UsageEventRow]: ...
    def list_prior_rating_results(self, tenant_id: UUID) -> list[PriorRatingRow]: ...
    def upsert_rating_period(
        self,
        row: RatingPeriodRow,
        *,
        conflict_fields: tuple[str, ...],
        update_fields: tuple[str, ...],
    ) -> None: ...
    def upsert_rating_result(
        self,
        row: RatingResultRow,
        *,
        conflict_fields: tuple[str, ...],
        update_fields: tuple[str, ...],
    ) -> None: ...


def overlapping_subscription(
    subscriptions: list[SubscriptionRow], tenant_id: UUID, period_start: date, period_end: date
) -> SubscriptionRow:
    eligible = [
        row
        for row in subscriptions
        if row.tenant_id == tenant_id
        and row.starts_on <= period_end
        and (row.ends_on is None or row.ends_on >= period_start)
    ]
    if not eligible:
        raise LookupError("rating subscription not found")
    return max(eligible, key=lambda row: row.starts_on)


def period_events(
    events: list[UsageEventRow],
    tenant_id: UUID,
    period_start: date,
    period_end: date,
    session_timezone: tzinfo,
) -> list[UsageEventRow]:
    return [
        row
        for row in events
        if row.tenant_id == tenant_id
        and period_start <= row.occurred_at.astimezone(session_timezone).date() <= period_end
    ]


def usage_rating(
    *,
    plans: list[PlanRow],
    subscriptions: list[SubscriptionRow],
    events: list[UsageEventRow],
    prior_results: list[PriorRatingRow],
    tenant_id: UUID,
    period_start: date,
    period_end: date,
    session_timezone: tzinfo,
) -> UsageRating:
    if period_end < period_start:
        raise ValueError("period_end must not precede period_start")
    subscription = overlapping_subscription(subscriptions, tenant_id, period_start, period_end)
    plan = next(row for row in plans if row.plan_id == subscription.plan_id)
    used = sum(
        row.units
        for row in period_events(
            events,
            tenant_id,
            period_start,
            period_end,
            session_timezone,
        )
    )
    month_index = period_start.year * 12 + period_start.month - 1 - 3
    year, month = divmod(month_index, 12)
    lower = date(year, month + 1, min(period_start.day, monthrange(year, month + 1)[1]))
    rollover = min(
        2 * plan.included_units,
        sum(
            row.rollover_units
            for row in prior_results
            if row.tenant_id == tenant_id and lower <= row.period_start < period_start
        ),
    )
    billable = max(used - rollover - plan.included_units, 0)
    first = min(billable, 101)
    second = max(billable - 101, 0)
    amount = (first * plan.overage_rate + second * plan.overage_rate * Decimal("1.5")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    if (
        subscription.status == "suspended"
        and subscription.suspended_on is not None
        and period_start <= subscription.suspended_on <= period_end
    ):
        fraction = Decimal((period_end - subscription.suspended_on).days + 1) / Decimal(
            (period_end - period_start).days + 1,
        )
        billable = int((billable * fraction).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        amount = (amount * fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return UsageRating(
        tenant_id,
        period_start,
        period_end,
        used,
        plan.included_units,
        rollover,
        billable,
        first,
        second,
        amount,
    )


def usage_summary(
    events: list[UsageEventRow],
    tenant_id: UUID,
    period_start: date,
    period_end: date,
    *,
    session_timezone: tzinfo,
) -> list[UsageSummary]:
    if period_end < period_start:
        raise ValueError("period_end must not precede period_start")
    grouped: dict[str, tuple[int, int]] = {}
    for row in period_events(events, tenant_id, period_start, period_end, session_timezone):
        count, units = grouped.get(row.kind, (0, 0))
        grouped[row.kind] = count + 1, units + row.units
    return [UsageSummary(kind, *grouped[kind]) for kind in sorted(grouped)]


def rate_tenant(
    repository: RatingRepository,
    tenant_id: UUID,
    period_start: date,
    period_end: date,
    *,
    session_timezone: tzinfo,
) -> UsageRating:
    return usage_rating(
        plans=repository.list_plans(),
        subscriptions=repository.list_subscriptions(tenant_id),
        events=repository.list_usage_events(tenant_id),
        prior_results=repository.list_prior_rating_results(tenant_id),
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        session_timezone=session_timezone,
    )


def finalize_rating(
    repository: RatingRepository,
    tenant_id: UUID,
    period_start: date,
    period_end: date,
    *,
    session_timezone: tzinfo,
) -> None:
    if period_end < period_start:
        raise ValueError("period_end must not precede period_start")
    subscription = overlapping_subscription(
        repository.list_subscriptions(tenant_id),
        tenant_id,
        period_start,
        period_end,
    )
    period_id = UUID(md5(f"{tenant_id}{period_start.isoformat()}".encode()).hexdigest())
    repository.upsert_rating_period(
        RatingPeriodRow(period_id, tenant_id, period_start, period_end),
        conflict_fields=("tenant_id", "period_start"),
        update_fields=("period_end",),
    )
    rating = rate_tenant(
        repository, tenant_id, period_start, period_end, session_timezone=session_timezone
    )
    repository.upsert_rating_result(
        RatingResultRow(
            UUID(md5(str(period_id).encode()).hexdigest()),
            period_id,
            subscription.subscription_id,
            rating.used_units,
            rating.quota_units,
            max(rating.quota_units - rating.used_units, 0),
            rating.billable_units,
            rating.overage_amount,
            datetime.combine(period_end, time.min, session_timezone),
        ),
        conflict_fields=("id",),
        update_fields=("used_units", "rollover_units", "billable_units", "overage_amount"),
    )
