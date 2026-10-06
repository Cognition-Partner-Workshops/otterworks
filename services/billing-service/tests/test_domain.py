from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from app.domain import (
    EntitlementRow,
    PlanRow,
    PriorRatingRow,
    RatingResultRow,
    SubscriptionRow,
    UsageEventRow,
    UsageSummaryRow,
    billable_units,
    catalog,
    change_plan,
    entitlement,
    finalize_rating,
    overage_amount,
    pg_numeric_divide,
    rate_usage,
    rating_period_id,
    rating_result_id,
    rating_subscription,
    rollover_units,
    suspension_fraction,
    tier_units,
    usage_rating,
    usage_summary,
    used_units,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
STARTER = UUID("10000000-0000-0000-0000-000000000001")
GROWTH = UUID("10000000-0000-0000-0000-000000000002")
SUBSCRIPTION = UUID("20000000-0000-0000-0000-000000000001")


class FakeRepository:
    def __init__(self, subscriptions: list[SubscriptionRow]) -> None:
        self.subscriptions = subscriptions
        self.updates: list[tuple[UUID, date, str]] = []
        self.inserted: list[tuple[UUID, UUID, UUID, date, str]] = []

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        return list(self.subscriptions)

    def update_subscription(self, subscription_id: UUID, ends_on: date, status: str) -> None:
        self.updates.append((subscription_id, ends_on, status))
        self.subscriptions = [
            replace(item, ends_on=ends_on, status=status)
            if item.subscription_id == subscription_id
            else item
            for item in self.subscriptions
        ]

    def insert_subscription(
        self,
        subscription_id: UUID,
        tenant_id: UUID,
        plan_id: UUID,
        starts_on: date,
        status: str,
    ) -> None:
        self.inserted.append((subscription_id, tenant_id, plan_id, starts_on, status))
        self.subscriptions.append(
            SubscriptionRow(subscription_id, tenant_id, plan_id, starts_on, None, status, None)
        )


@pytest.mark.rule("PLANS-001")
def test_catalog_is_sorted_in_plain_python() -> None:
    plans = [
        PlanRow(GROWTH, "GROWTH", "growth", Decimal("149"), 500, Decimal("0.035"), True),
        PlanRow(STARTER, "STARTER", "starter", Decimal("49"), 100, Decimal("0.055"), True),
    ]
    assert [item.code for item in catalog(plans)] == ["STARTER", "GROWTH"]


@pytest.mark.rule("PLANS-002")
def test_entitlement_selects_effective_subscription() -> None:
    rows = [
        EntitlementRow(
            TENANT, "STARTER", "starter", Decimal("49"), 100, "active", None, date(2026, 1, 1)
        ),
        EntitlementRow(
            TENANT, "GROWTH", "growth", Decimal("149"), 500, "active", None, date(2026, 3, 1)
        ),
    ]
    assert entitlement(rows, TENANT, date(2026, 2, 28)).plan_code == "STARTER"


@pytest.mark.rule("PLANS-002")
def test_entitlement_preserves_suspended_status() -> None:
    row = EntitlementRow(
        TENANT, "GROWTH", "growth", Decimal("149"), 500, "suspended", None, date(2026, 1, 1)
    )
    assert entitlement([row], TENANT, date(2026, 2, 28)).subscription_status == "suspended"


@pytest.mark.rule("PLANS-003")
def test_change_plan_closes_prior_subscription() -> None:
    repository = FakeRepository(
        [SubscriptionRow(SUBSCRIPTION, TENANT, STARTER, date(2026, 1, 1), None, "active", None)]
    )
    change_plan(repository, TENANT, GROWTH, date(2026, 3, 1))
    assert repository.updates == [(SUBSCRIPTION, date(2026, 2, 28), "active")]


@pytest.mark.rule("PLANS-004")
def test_change_plan_uses_stable_uuid5_and_preserves_history() -> None:
    repository = FakeRepository(
        [SubscriptionRow(SUBSCRIPTION, TENANT, STARTER, date(2026, 1, 1), None, "active", None)]
    )
    result, created = change_plan(repository, TENANT, GROWTH, date(2026, 3, 1))
    assert len(result) == 2
    assert created.plan_id == GROWTH
    assert repository.inserted[0][0].version == 5


def test_change_plan_reports_new_subscription_with_later_dated_history() -> None:
    later = SubscriptionRow(
        UUID("20000000-0000-0000-0000-000000000002"),
        TENANT,
        GROWTH,
        date(2026, 6, 1),
        None,
        "active",
        None,
    )
    repository = FakeRepository(
        [
            SubscriptionRow(
                SUBSCRIPTION, TENANT, STARTER, date(2026, 1, 1), None, "active", None
            ),
            later,
        ]
    )
    subscriptions, created = change_plan(repository, TENANT, GROWTH, date(2026, 3, 1))
    assert subscriptions[-1].starts_on == date(2026, 6, 1)
    assert created.starts_on == date(2026, 3, 1)


def test_generated_seed_is_current() -> None:
    from scripts.generate_seed import generate

    seed_path = Path(__file__).parents[1] / "db" / "seed.sql"
    assert seed_path.read_text() == generate()


FEB_START = date(2026, 2, 1)
FEB_END = date(2026, 2, 28)
STARTER_PLAN = PlanRow(STARTER, "STARTER", "starter", Decimal("49"), 100, Decimal("0.055"), True)
GROWTH_PLAN = PlanRow(GROWTH, "GROWTH", "growth", Decimal("149"), 500, Decimal("0.035"), True)
SCALE = UUID("10000000-0000-0000-0000-000000000003")
SCALE_PLAN = PlanRow(SCALE, "SCALE", "scale", Decimal("499"), 2000, Decimal("0.02"), True)


def subscription(
    plan_id: UUID = STARTER,
    starts_on: date = date(2026, 1, 1),
    ends_on: date | None = None,
    status: str = "active",
    suspended_on: date | None = None,
    subscription_id: UUID = SUBSCRIPTION,
) -> SubscriptionRow:
    return SubscriptionRow(
        subscription_id, TENANT, plan_id, starts_on, ends_on, status, suspended_on
    )


def event(occurred_on: date, units: int, kind: str = "api") -> UsageEventRow:
    return UsageEventRow(TENANT, occurred_on, units, kind)


def rate(
    sub: SubscriptionRow | None,
    plan: PlanRow | None,
    events: list[UsageEventRow],
    prior: list[PriorRatingRow] | None = None,
):
    return rate_usage(TENANT, FEB_START, FEB_END, sub, plan, events, prior or [])


TENANT_ONE_PRIOR = [
    PriorRatingRow(date(2025, 11, 1), 100),
    PriorRatingRow(date(2025, 12, 1), 100),
    PriorRatingRow(date(2026, 1, 1), 100),
]


class FakeRatingRepository:
    def __init__(
        self,
        subscriptions: list[SubscriptionRow],
        plans: list[PlanRow],
        events: list[UsageEventRow],
        periods: dict[UUID, tuple[UUID, date, date]] | None = None,
        results: dict[UUID, tuple[UUID, UUID, RatingResultRow, date]] | None = None,
    ) -> None:
        self.subscriptions = subscriptions
        self.plans = {plan.plan_id: plan for plan in plans}
        self.events = events
        self.periods = periods or {}
        self.results = results or {}

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        return [item for item in self.subscriptions if item.tenant_id == tenant_id]

    def find_plan(self, plan_id: UUID) -> PlanRow | None:
        return self.plans.get(plan_id)

    def list_usage_events(self, tenant_id: UUID) -> list[UsageEventRow]:
        return [item for item in self.events if item.tenant_id == tenant_id]

    def list_prior_ratings(self, tenant_id: UUID) -> list[PriorRatingRow]:
        return [
            PriorRatingRow(self.periods[period_id][1], result.rollover_units)
            for period_id, _subscription_id, result, _created in self.results.values()
            if self.periods[period_id][0] == tenant_id
        ]

    def upsert_rating_period(
        self, period_id: UUID, tenant_id: UUID, period_start: date, period_end: date
    ) -> None:
        for existing_id, (existing_tenant, existing_start, _end) in self.periods.items():
            if (existing_tenant, existing_start) == (tenant_id, period_start):
                self.periods[existing_id] = (tenant_id, period_start, period_end)
                return
        self.periods[period_id] = (tenant_id, period_start, period_end)

    def upsert_rating_result(
        self,
        result_id: UUID,
        period_id: UUID,
        subscription_id: UUID,
        result: RatingResultRow,
        created_on: date,
    ) -> None:
        if result_id in self.results:
            stored_period, stored_subscription, stored, stored_created = self.results[result_id]
            result = replace(stored, **{
                field: getattr(result, field)
                for field in ("used_units", "rollover_units", "billable_units", "overage_amount")
            })
            self.results[result_id] = (stored_period, stored_subscription, result, stored_created)
            return
        self.results[result_id] = (period_id, subscription_id, result, created_on)

    def find_rating_results(self, tenant_id: UUID, period_start: date) -> list[RatingResultRow]:
        return [
            result
            for period_id, _subscription_id, result, _created in self.results.values()
            if self.periods[period_id][:2] == (tenant_id, period_start)
        ]


@pytest.mark.rule("RATING-001")
def test_rating_uses_latest_overlapping_subscription() -> None:
    old = subscription(STARTER, date(2025, 6, 1), date(2026, 2, 9))
    new = subscription(GROWTH, date(2026, 2, 10), subscription_id=GROWTH)
    later = subscription(STARTER, date(2026, 3, 1), subscription_id=STARTER)
    assert rating_subscription([old, new, later], FEB_START, FEB_END) == new
    ended = subscription(STARTER, date(2025, 1, 1), date(2026, 1, 31))
    assert rating_subscription([ended], FEB_START, FEB_END) is None


@pytest.mark.rule("RATING-001")
def test_used_units_count_period_dates_inclusive() -> None:
    events = [
        event(date(2026, 1, 31), 1),
        event(FEB_START, 10),
        event(FEB_END, 20),
        event(date(2026, 3, 1), 300),
    ]
    assert used_units(events, FEB_START, FEB_END) == 30
    assert used_units([], FEB_START, FEB_END) == 0


@pytest.mark.rule("RATING-001")
def test_rating_without_prior_periods_matches_tenant_seven() -> None:
    rating = rate(subscription(), STARTER_PLAN, [event(date(2026, 2, 10), 260)])
    assert (rating.used_units, rating.quota_units) == (260, 100)
    assert (rating.rollover_units, rating.billable_units) == (0, 160)


@pytest.mark.rule("RATING-001")
def test_rating_without_subscription_has_null_quota_and_amount() -> None:
    rating = rate(None, None, [event(date(2026, 2, 10), 260)], TENANT_ONE_PRIOR)
    assert rating.used_units == 260
    assert rating.quota_units is None
    assert rating.overage_amount is None
    assert (rating.billable_units, rating.first_tier_units, rating.second_tier_units) == (0, 0, 0)
    assert rating.rollover_units == 300


@pytest.mark.rule("RATING-002")
def test_rollover_sums_three_month_window_and_caps_at_twice_quota() -> None:
    assert rollover_units(TENANT_ONE_PRIOR, FEB_START, 100) == 200
    assert rollover_units(TENANT_ONE_PRIOR, FEB_START, 500) == 300
    assert rollover_units(TENANT_ONE_PRIOR, date(2026, 3, 1), 500) == 200
    current = [*TENANT_ONE_PRIOR, PriorRatingRow(FEB_START, 100)]
    assert rollover_units(current, FEB_START, 500) == 300


@pytest.mark.rule("RATING-002")
def test_rollover_window_clamps_month_end_like_postgres() -> None:
    prior = [PriorRatingRow(date(2026, 2, 28), 7), PriorRatingRow(date(2026, 2, 27), 11)]
    assert rollover_units(prior, date(2026, 5, 31), 100) == 7


@pytest.mark.rule("RATING-002")
def test_consumed_rollover_is_applied_again_next_period() -> None:
    prior = [*TENANT_ONE_PRIOR, PriorRatingRow(FEB_START, 0)]
    assert rollover_units(prior, date(2026, 3, 1), 100) == 200


@pytest.mark.rule("RATING-002")
@pytest.mark.rule("RATING-003")
def test_rollover_covers_overage_for_tenant_one() -> None:
    rating = rate(subscription(), STARTER_PLAN, [event(date(2026, 2, 10), 260)], TENANT_ONE_PRIOR)
    assert rating.rollover_units == 200
    assert rating.billable_units == 0
    assert rating.overage_amount == Decimal("0.00")


@pytest.mark.rule("RATING-003")
def test_billable_units_floor_at_zero() -> None:
    assert billable_units(260, 0, 100) == 160
    assert billable_units(260, 200, 100) == 0
    assert billable_units(700, 0, 500) == 200


@pytest.mark.rule("RATING-004")
def test_first_tier_holds_101_units() -> None:
    assert tier_units(0) == (0, 0)
    assert tier_units(100) == (100, 0)
    assert tier_units(101) == (101, 0)
    assert tier_units(102) == (101, 1)
    assert tier_units(201) == (101, 100)


@pytest.mark.rule("RATING-004")
def test_tier_units_are_not_prorated() -> None:
    suspended = subscription(GROWTH, status="suspended", suspended_on=date(2026, 2, 15))
    rating = rate(suspended, GROWTH_PLAN, [event(date(2026, 2, 10), 700)])
    assert (rating.first_tier_units, rating.second_tier_units) == (101, 99)
    assert rating.billable_units == 100


@pytest.mark.rule("RATING-005")
def test_overage_amount_rounds_half_up_once() -> None:
    assert overage_amount(101, 0, Decimal("0.055")) == Decimal("5.56")
    assert overage_amount(15, 0, Decimal("0.055")) == Decimal("0.83")
    assert overage_amount(101, 100, Decimal("0.02")) == Decimal("5.02")
    assert overage_amount(101, 99, Decimal("0.035")) == Decimal("8.73")


@pytest.mark.rule("RATING-005")
def test_rating_amounts_match_recorded_scenarios() -> None:
    starter = rate(subscription(), STARTER_PLAN, [event(FEB_END, 201)])
    assert (starter.first_tier_units, starter.overage_amount) == (101, Decimal("5.56"))
    scale = rate(subscription(SCALE), SCALE_PLAN, [event(date(2026, 2, 10), 2201, "compute")])
    assert (scale.first_tier_units, scale.second_tier_units) == (101, 100)
    assert scale.overage_amount == Decimal("5.02")


@pytest.mark.rule("RATING-006")
def test_suspension_prorates_units_and_amount_for_tenant_two() -> None:
    suspended = subscription(GROWTH, status="suspended", suspended_on=date(2026, 2, 15))
    rating = rate(suspended, GROWTH_PLAN, [event(date(2026, 2, 10), 700)])
    assert rating.billable_units == 100
    assert rating.overage_amount == Decimal("4.37")


@pytest.mark.rule("RATING-006")
def test_suspension_rounds_amount_twice() -> None:
    suspended = subscription(GROWTH, status="suspended", suspended_on=date(2026, 2, 15))
    rating = rate(suspended, GROWTH_PLAN, [event(date(2026, 2, 10), 650)])
    assert rating.overage_amount == Decimal("3.06")
    assert rating.billable_units == 75


@pytest.mark.rule("RATING-006")
def test_suspension_fraction_counts_days_from_suspension_to_period_end() -> None:
    early = subscription(GROWTH, status="suspended", suspended_on=date(2026, 2, 5))
    late = subscription(GROWTH, status="suspended", suspended_on=date(2026, 2, 25))
    events = [event(date(2026, 2, 10), 650)]
    assert rate(early, GROWTH_PLAN, events).overage_amount == Decimal("5.24")
    assert rate(late, GROWTH_PLAN, events).overage_amount == Decimal("0.87")
    assert suspension_fraction(early, FEB_START, FEB_END) == Decimal("0.85714285714285714286")


@pytest.mark.rule("RATING-006")
def test_suspension_outside_period_or_not_suspended_is_not_prorated() -> None:
    events = [event(date(2026, 2, 10), 700)]
    before = subscription(GROWTH, status="suspended", suspended_on=date(2026, 1, 31))
    active = subscription(GROWTH, status="active", suspended_on=date(2026, 2, 15))
    assert suspension_fraction(before, FEB_START, FEB_END) is None
    assert suspension_fraction(active, FEB_START, FEB_END) is None
    assert rate(active, GROWTH_PLAN, events).overage_amount == Decimal("8.73")


@pytest.mark.rule("RATING-006")
def test_numeric_division_uses_postgres_scale() -> None:
    assert pg_numeric_divide(14, 28) == Decimal("0.50000000000000000000")
    assert pg_numeric_divide(1, 3) == Decimal("0.33333333333333333333")
    assert pg_numeric_divide(2, 3) == Decimal("0.66666666666666666667")
    assert pg_numeric_divide(28, 28) == Decimal("1.00000000000000000000")


@pytest.mark.rule("RATING-007")
def test_usage_summary_groups_by_kind_in_period() -> None:
    events = [
        event(date(2026, 2, 6), 30, "storage"),
        event(date(2026, 2, 5), 20, "api"),
        event(FEB_END, 5, "api"),
        event(date(2026, 3, 1), 99, "compute"),
    ]
    assert usage_summary(events, FEB_START, FEB_END) == [
        UsageSummaryRow("api", 2, 25),
        UsageSummaryRow("storage", 1, 30),
    ]
    assert usage_summary([], FEB_START, FEB_END) == []


def tenant_one_repository() -> FakeRatingRepository:
    periods = {
        UUID(f"40000000-0000-0000-0000-00000000000{index}"): (TENANT, prior.period_start, end)
        for index, (prior, end) in enumerate(
            zip(
                TENANT_ONE_PRIOR,
                [date(2025, 11, 30), date(2025, 12, 31), date(2026, 1, 31)],
                strict=True,
            ),
            start=1,
        )
    }
    results = {
        UUID(f"50000000-0000-0000-0000-00000000000{index}"): (
            period_id,
            SUBSCRIPTION,
            RatingResultRow(0, 100, 100, 0, Decimal("0.00")),
            end,
        )
        for index, (period_id, (_tenant, _start, end)) in enumerate(periods.items(), start=1)
    }
    return FakeRatingRepository(
        [subscription()], [STARTER_PLAN], [event(date(2026, 2, 10), 260)], periods, results
    )


@pytest.mark.rule("RATING-008")
def test_finalize_stores_unused_quota_as_rollover() -> None:
    repository = tenant_one_repository()
    rows = finalize_rating(repository, TENANT, FEB_START, FEB_END)
    assert rows == [RatingResultRow(260, 100, 0, 0, Decimal("0.00"))]
    period_id = rating_period_id(TENANT, FEB_START)
    assert repository.periods[period_id] == (TENANT, FEB_START, FEB_END)
    assert repository.results[rating_result_id(period_id)][3] == FEB_END


@pytest.mark.rule("RATING-008")
def test_finalize_stores_unused_quota_not_applied_rollover() -> None:
    repository = FakeRatingRepository(
        [subscription()], [STARTER_PLAN], [event(date(2026, 2, 10), 40)]
    )
    assert finalize_rating(repository, TENANT, FEB_START, FEB_END) == [
        RatingResultRow(40, 100, 60, 0, Decimal("0.00"))
    ]


@pytest.mark.rule("RATING-008")
def test_refinalize_overwrites_the_same_result_row() -> None:
    repository = FakeRatingRepository(
        [subscription()], [STARTER_PLAN], [event(date(2026, 2, 10), 40)]
    )
    finalize_rating(repository, TENANT, FEB_START, FEB_END)
    repository.events.append(event(date(2026, 2, 11), 200))
    rows = finalize_rating(repository, TENANT, FEB_START, date(2026, 2, 27))
    assert rows == [RatingResultRow(240, 100, 0, 140, Decimal("8.77"))]
    assert len(repository.results) == 1
    period_id = rating_period_id(TENANT, FEB_START)
    assert repository.periods[period_id][2] == date(2026, 2, 27)
    assert repository.results[rating_result_id(period_id)][3] == FEB_END


@pytest.mark.rule("RATING-008")
def test_rating_ids_match_legacy_md5_uuids() -> None:
    period_id = rating_period_id(TENANT, FEB_START)
    assert period_id == UUID("27cdd7d2-32b3-afc0-922c-e9858e767b6d")
    assert rating_result_id(period_id) == UUID("175fe5b7-8f91-1c3a-8586-1ef5c455fc9a")


def test_usage_rating_reads_repository() -> None:
    repository = tenant_one_repository()
    rating = usage_rating(repository, TENANT, FEB_START, FEB_END)
    assert (rating.rollover_units, rating.billable_units) == (200, 0)
