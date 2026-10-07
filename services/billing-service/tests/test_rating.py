from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.domain import (
    NoSubscriptionError,
    PlanRow,
    RatingHistoryRow,
    RatingPeriodRow,
    RatingResultRow,
    SubscriptionRow,
    UsageEventRow,
    billable_units,
    finalize_rating,
    months_before,
    overage_amount,
    pg_numeric_quotient,
    prorate,
    rate_usage,
    rating_period_id,
    rating_result_id,
    rollover_units,
    select_subscription,
    suspension_factor,
    tier_split,
    usage_summary,
    used_units,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
STARTER = UUID("10000000-0000-0000-0000-000000000001")
GROWTH = UUID("10000000-0000-0000-0000-000000000002")
SUB_OLD = UUID("20000000-0000-0000-0000-000000000001")
SUB_NEW = UUID("20000000-0000-0000-0000-000000000002")
FEB_START = date(2026, 2, 1)
FEB_END = date(2026, 2, 28)

PLANS = [
    PlanRow(STARTER, "STARTER", "starter", Decimal("49.00"), 100, Decimal("0.055000"), True),
    PlanRow(GROWTH, "GROWTH", "growth", Decimal("149.00"), 500, Decimal("0.045000"), True),
]


def subscription(
    subscription_id: UUID = SUB_OLD,
    plan_id: UUID = STARTER,
    starts_on: date = date(2025, 1, 1),
    ends_on: date | None = None,
    status: str = "active",
    suspended_on: date | None = None,
) -> SubscriptionRow:
    return SubscriptionRow(
        subscription_id, TENANT, plan_id, starts_on, ends_on, status, suspended_on
    )


def event(occurred_at: datetime, units: int, kind: str = "api") -> UsageEventRow:
    return UsageEventRow(TENANT, occurred_at, units, kind)


class FakeRatingRepository:
    def __init__(
        self,
        subscriptions: list[SubscriptionRow],
        events: list[UsageEventRow] | None = None,
        history: list[RatingHistoryRow] | None = None,
    ) -> None:
        self.subscriptions = subscriptions
        self.events = events or []
        self.history = history or []
        self.periods: dict[UUID, RatingPeriodRow] = {}
        self.results: dict[UUID, RatingResultRow] = {}

    def list_plans(self) -> list[PlanRow]:
        return PLANS

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        return [item for item in self.subscriptions if item.tenant_id == tenant_id]

    def list_usage_events(self, tenant_id: UUID) -> list[UsageEventRow]:
        return [item for item in self.events if item.tenant_id == tenant_id]

    def list_rating_history(self, _tenant_id: UUID) -> list[RatingHistoryRow]:
        return self.history

    def find_rating_period(self, tenant_id: UUID, period_start: date) -> RatingPeriodRow | None:
        return next(
            (
                item
                for item in self.periods.values()
                if item.tenant_id == tenant_id and item.period_start == period_start
            ),
            None,
        )

    def insert_rating_period(self, period: RatingPeriodRow) -> None:
        self.periods[period.period_id] = period

    def update_rating_period_end(self, period_id: UUID, period_end: date) -> None:
        current = self.periods[period_id]
        self.periods[period_id] = RatingPeriodRow(
            current.period_id, current.tenant_id, current.period_start, period_end
        )

    def find_rating_result(self, result_id: UUID) -> RatingResultRow | None:
        return self.results.get(result_id)

    def insert_rating_result(self, result: RatingResultRow) -> None:
        self.results[result.result_id] = result

    def update_rating_result(self, result: RatingResultRow) -> None:
        current = self.results[result.result_id]
        self.results[result.result_id] = RatingResultRow(
            current.result_id,
            current.period_id,
            current.subscription_id,
            result.used_units,
            current.quota_units,
            result.rollover_units,
            result.billable_units,
            result.overage_amount,
            current.created_at,
        )

    def list_rating_results(self, tenant_id: UUID, period_start: date) -> list[RatingResultRow]:
        period = self.find_rating_period(tenant_id, period_start)
        return [
            item
            for item in self.results.values()
            if period and item.period_id == period.period_id
        ]


@pytest.mark.rule("RATING-R01")
def test_latest_overlapping_subscription_supplies_the_plan() -> None:
    expired = subscription(SUB_OLD, STARTER, date(2025, 1, 1), date(2026, 1, 31), "cancelled")
    older = subscription(SUB_OLD, STARTER, date(2025, 6, 1), date(2026, 2, 14), "cancelled")
    latest = subscription(SUB_NEW, GROWTH, date(2026, 2, 15))
    future = subscription(SUB_NEW, GROWTH, date(2026, 3, 1))

    assert select_subscription([expired, future], FEB_START, FEB_END) is None
    assert select_subscription([older, latest, future], FEB_START, FEB_END) == latest
    rating = rate_usage(FakeRatingRepository([older, latest]), TENANT, FEB_START, FEB_END)
    assert (rating.subscription_id, rating.quota_units) == (SUB_NEW, 500)


@pytest.mark.rule("RATING-R01")
def test_rating_without_an_overlapping_subscription_is_not_found(monkeypatch) -> None:
    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def no_subscription(*_args: object) -> None:
        raise NoSubscriptionError(TENANT)

    with pytest.raises(NoSubscriptionError):
        rate_usage(FakeRatingRepository([]), TENANT, FEB_START, FEB_END)
    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "rate_usage", no_subscription)
    monkeypatch.setattr(main, "finalize_rating", no_subscription)
    query = "period_start=2026-02-01&period_end=2026-02-28"
    with TestClient(main.app) as client:
        rating = client.get(f"/api/tenants/{TENANT}/usage-rating?{query}")
        finalized = client.post(
            f"/api/tenants/{TENANT}/rating-finalizations",
            json={"period_start": "2026-02-01", "period_end": "2026-02-28"},
        )
    assert rating.status_code == 404
    assert finalized.status_code == 404


@pytest.mark.rule("RATING-R02")
def test_used_units_count_utc_calendar_days_inclusive() -> None:
    events = [
        event(datetime(2026, 1, 31, 23, 59, 59, tzinfo=UTC), 1),
        event(datetime(2026, 2, 1, 0, 0, tzinfo=UTC), 10),
        event(datetime.fromisoformat("2026-02-28T23:30:00-05:00"), 1000),
        event(datetime(2026, 2, 28, 23, 59, 59, tzinfo=UTC), 100),
        event(datetime(2026, 3, 1, 0, 0, tzinfo=UTC), 10000),
    ]
    assert used_units(events, FEB_START, FEB_END) == 110


@pytest.mark.rule("RATING-R03")
def test_rollover_is_a_gross_capped_sum_over_three_prior_months() -> None:
    history = [
        RatingHistoryRow(date(2025, 10, 1), 1000),
        RatingHistoryRow(date(2025, 11, 1), 60),
        RatingHistoryRow(date(2026, 1, 1), 50),
        RatingHistoryRow(FEB_START, 1000),
    ]
    assert months_before(date(2026, 5, 31), 3) == date(2026, 2, 28)
    assert rollover_units(history, FEB_START, included_units=100) == 110
    assert rollover_units(history, FEB_START, included_units=50) == 100
    assert rollover_units([], FEB_START, included_units=100) == 0


@pytest.mark.rule("RATING-R04")
def test_rollover_is_consumed_before_included_quota() -> None:
    assert billable_units(used=260, rollover=0, included_units=100) == 160
    assert billable_units(used=260, rollover=200, included_units=100) == 0
    assert billable_units(used=350, rollover=200, included_units=100) == 50


@pytest.mark.rule("RATING-R05")
def test_first_tier_holds_101_units() -> None:
    assert tier_split(100) == (100, 0)
    assert tier_split(101) == (101, 0)
    assert tier_split(102) == (101, 1)
    assert tier_split(0) == (0, 0)


@pytest.mark.rule("RATING-R06")
def test_overage_is_rounded_once_half_up() -> None:
    rate = Decimal("0.055000")
    assert overage_amount(101, 0, rate) == Decimal("5.56")
    assert overage_amount(101, 1, rate) == Decimal("5.64")
    assert overage_amount(1, 1, Decimal("0.010000")) == Decimal("0.03")


@pytest.mark.rule("RATING-R07")
def test_suspension_prorates_billable_and_amount_but_not_tiers() -> None:
    suspended = subscription(status="suspended", suspended_on=date(2026, 2, 15))
    repository = FakeRatingRepository(
        [suspended], [event(datetime(2026, 2, 10, tzinfo=UTC), 300)]
    )
    rating = rate_usage(repository, TENANT, FEB_START, FEB_END)

    assert (rating.first_tier_units, rating.second_tier_units) == (101, 99)
    assert rating.billable_units == 100
    assert rating.overage_amount == Decimal("6.86")
    active = subscription(suspended_on=date(2026, 2, 15))
    assert suspension_factor(active, FEB_START, FEB_END) is None
    assert suspension_factor(
        subscription(status="suspended", suspended_on=date(2026, 3, 1)), FEB_START, FEB_END
    ) is None


@pytest.mark.rule("RATING-R07")
def test_proration_copies_postgres_numeric_quotient_precision() -> None:
    factor = pg_numeric_quotient(5, 6)
    assert factor == Decimal("0.83333333333333333333")
    assert pg_numeric_quotient(1, 3) == Decimal("0.33333333333333333333")
    assert pg_numeric_quotient(10, 30) == Decimal("0.33333333333333333333")
    assert pg_numeric_quotient(14, 28) == Decimal("0.50000000000000000000")
    assert prorate(3, Decimal("0.03"), factor) == (2, Decimal("0.02"))
    assert prorate(1, Decimal("0.01"), Decimal("0.5")) == (1, Decimal("0.01"))


@pytest.mark.rule("RATING-R08")
def test_usage_summary_groups_kinds_with_events_in_order() -> None:
    events = [
        event(datetime(2026, 2, 3, tzinfo=UTC), 20, "storage"),
        event(datetime(2026, 2, 2, tzinfo=UTC), 5, "api"),
        event(datetime(2026, 2, 28, 23, 59, tzinfo=UTC), 15, "api"),
        event(datetime(2026, 3, 1, tzinfo=UTC), 99, "compute"),
    ]
    rows = usage_summary(events, FEB_START, FEB_END)
    assert [(row.kind, row.event_count, row.units) for row in rows] == [
        ("api", 2, 20),
        ("storage", 1, 20),
    ]


@pytest.mark.rule("RATING-R09")
def test_finalize_upserts_the_period_with_a_legacy_md5_id() -> None:
    repository = FakeRatingRepository([subscription()])
    period_id = rating_period_id(TENANT, FEB_START)
    assert period_id == UUID("27cdd7d2-32b3-afc0-922c-e9858e767b6d")

    finalize_rating(repository, TENANT, FEB_START, date(2026, 2, 27))
    finalize_rating(repository, TENANT, FEB_START, FEB_END)

    assert list(repository.periods) == [period_id]
    assert repository.periods[period_id].period_end == FEB_END


@pytest.mark.rule("RATING-R10")
def test_finalize_stores_unused_quota_and_keeps_first_quota() -> None:
    old = subscription()
    repository = FakeRatingRepository(
        [old],
        [event(datetime(2026, 2, 10, tzinfo=UTC), 40)],
        [RatingHistoryRow(date(2026, 1, 1), 100)],
    )
    period_id = rating_period_id(TENANT, FEB_START)

    [first] = finalize_rating(repository, TENANT, FEB_START, FEB_END)
    assert first.result_id == rating_result_id(period_id)
    assert (first.used_units, first.quota_units, first.rollover_units) == (40, 100, 60)
    assert first.created_at == datetime(2026, 2, 28, tzinfo=UTC)

    repository.subscriptions = [
        SubscriptionRow(SUB_NEW, TENANT, GROWTH, date(2026, 2, 1), None, "active", None)
    ]
    repository.events.append(event(datetime(2026, 2, 11, tzinfo=UTC), 760))
    [second] = finalize_rating(repository, TENANT, FEB_START, FEB_END)
    assert (second.quota_units, second.subscription_id) == (100, SUB_OLD)
    assert (second.used_units, second.rollover_units, second.billable_units) == (800, 0, 200)
    assert second.overage_amount == Decimal("11.23")
