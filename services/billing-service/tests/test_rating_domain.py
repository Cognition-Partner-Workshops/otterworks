from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.domain import (
    PriorRollover,
    Rating,
    RatingResultRow,
    RatingSubscription,
    UsageEvent,
    finalize_rating,
    legacy_md5_uuid,
    pg_integer_ratio,
    rate_usage,
    rating_period_id,
    round_half_away,
    select_rated_subscription,
    subtract_months,
    summarize_usage,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
FEB_START = date(2026, 2, 1)
FEB_END = date(2026, 2, 28)
STARTER_RATE = Decimal("0.055000")
GROWTH_RATE = Decimal("0.035000")
SCALE_RATE = Decimal("0.020000")


def subscription(
    included: int = 100,
    rate: Decimal = STARTER_RATE,
    *,
    starts_on: date = date(2026, 1, 1),
    ends_on: date | None = None,
    status: str = "active",
    suspended_on: date | None = None,
    subscription_id: str = "20000000-0000-0000-0000-000000000001",
) -> RatingSubscription:
    return RatingSubscription(
        UUID(subscription_id),
        UUID("10000000-0000-0000-0000-000000000001"),
        starts_on,
        ends_on,
        status,
        suspended_on,
        included,
        rate,
    )


def event(units: int, when: str = "2026-02-10T10:00:00+00:00", kind: str = "api") -> UsageEvent:
    return UsageEvent(datetime.fromisoformat(when), units, kind)


def rate(subscriptions, events, prior=()) -> Rating:
    return rate_usage(TENANT, FEB_START, FEB_END, list(subscriptions), list(events), list(prior))


@pytest.mark.rule("RATING-001")
def test_latest_overlapping_subscription_is_rated_regardless_of_status() -> None:
    older = subscription(
        starts_on=date(2025, 6, 1), subscription_id="20000000-0000-0000-0000-00000000000a"
    )
    newer = subscription(500, GROWTH_RATE, status="cancelled", ends_on=date(2026, 2, 3))
    future = subscription(2000, SCALE_RATE, starts_on=date(2026, 3, 1))
    selected = select_rated_subscription([older, newer, future], FEB_START, FEB_END)
    assert selected == newer
    assert rate([older, newer, future], [event(700)]).quota_units == 500


@pytest.mark.rule("RATING-001")
def test_missing_subscription_reproduces_legacy_null_row() -> None:
    rating = rate([], [event(260)], [PriorRollover(date(2026, 1, 1), 300)])
    assert (rating.quota_units, rating.overage_amount) == (None, None)
    assert (rating.used_units, rating.rollover_units, rating.billable_units) == (260, 300, 0)


@pytest.mark.rule("RATING-002")
def test_used_units_use_inclusive_utc_dates() -> None:
    events = [
        event(1, "2026-01-31T23:59:59+00:00"),
        event(2, "2026-02-01T00:00:00+00:00"),
        event(4, "2026-02-28T23:59:59+00:00"),
        event(8, "2026-03-01T00:30:00+01:00"),
        event(16, "2026-03-01T00:00:00+00:00"),
    ]
    assert rate([subscription()], events).used_units == 14


@pytest.mark.rule("RATING-003")
def test_rollover_window_is_three_months_and_capped_at_twice_included() -> None:
    prior = [
        PriorRollover(date(2025, 10, 31), 1000),
        PriorRollover(date(2025, 11, 1), 100),
        PriorRollover(date(2025, 12, 1), 100),
        PriorRollover(date(2026, 1, 1), 100),
        PriorRollover(date(2026, 2, 1), 1000),
    ]
    assert rate([subscription()], [event(260)], prior).rollover_units == 200
    assert rate([subscription()], [event(260)], prior[1:2]).rollover_units == 100
    assert rate([subscription()], [event(260)]).rollover_units == 0


@pytest.mark.rule("RATING-003")
def test_rollover_window_clamps_month_ends_like_postgres() -> None:
    assert subtract_months(date(2026, 5, 31), 3) == date(2026, 2, 28)
    assert subtract_months(date(2026, 2, 1), 3) == date(2025, 11, 1)


@pytest.mark.rule("RATING-004")
def test_billable_units_subtract_rollover_and_included_units() -> None:
    assert rate([subscription()], [event(260)]).billable_units == 160
    prior = [PriorRollover(date(2026, 1, 1), 300)]
    assert rate([subscription()], [event(260)], prior).billable_units == 0


@pytest.mark.rule("RATING-005")
@pytest.mark.parametrize(
    ("used", "first", "second"),
    [(201, 101, 0), (202, 101, 1), (100, 0, 0), (2201 - 1900, 101, 100)],
)
def test_first_tier_holds_101_units(used: int, first: int, second: int) -> None:
    rating = rate([subscription()], [event(used)])
    assert (rating.first_tier_units, rating.second_tier_units) == (first, second)


@pytest.mark.rule("RATING-006")
def test_overage_rounds_once_half_away_from_zero() -> None:
    assert rate([subscription()], [event(201)]).overage_amount == Decimal("5.56")
    scale = subscription(2000, SCALE_RATE)
    assert rate([scale], [event(2201)]).overage_amount == Decimal("5.02")
    assert round_half_away(Decimal("0.125"), 2) == Decimal("0.13")


@pytest.mark.rule("RATING-007")
def test_suspension_prorates_billable_and_rounded_amount_but_not_tiers() -> None:
    suspended = subscription(500, GROWTH_RATE, status="suspended", suspended_on=date(2026, 2, 15))
    rating = rate([suspended], [event(700)])
    assert rating.billable_units == 100
    assert rating.overage_amount == Decimal("4.37")
    assert (rating.first_tier_units, rating.second_tier_units) == (101, 99)


@pytest.mark.rule("RATING-007")
def test_suspension_bills_the_tail_of_the_period() -> None:
    suspended = subscription(500, GROWTH_RATE, status="suspended", suspended_on=date(2026, 2, 22))
    rating = rate([suspended], [event(700)])
    assert rating.billable_units == 50
    assert rating.overage_amount == Decimal("2.18")
    outside = subscription(500, GROWTH_RATE, status="suspended", suspended_on=date(2026, 3, 2))
    assert rate([outside], [event(700)]).billable_units == 200


@pytest.mark.rule("RATING-007")
def test_suspension_fraction_uses_postgres_numeric_scale() -> None:
    assert pg_integer_ratio(14, 28) == Decimal("0.50000000000000000000")
    assert pg_integer_ratio(13, 28) == Decimal("0.46428571428571428571")
    assert pg_integer_ratio(1, 31) == Decimal("0.03225806451612903226")
    assert pg_integer_ratio(28, 28) == Decimal("1.00000000000000000000")


@pytest.mark.rule("RATING-008")
def test_usage_summary_groups_by_kind_in_order() -> None:
    events = [
        event(30, "2026-02-06T10:00:00+00:00", "storage"),
        event(20, "2026-02-05T10:00:00+00:00", "api"),
        event(5, "2026-02-07T10:00:00+00:00", "api"),
        event(99, "2026-03-01T00:00:00+00:00", "compute"),
    ]
    rows = summarize_usage(events, FEB_START, FEB_END)
    assert [(row.kind, row.event_count, row.units) for row in rows] == [
        ("api", 2, 25),
        ("storage", 1, 30),
    ]


class FakeRatingRepository:
    def __init__(self, subscriptions, events, prior=()) -> None:
        self.subscriptions = list(subscriptions)
        self.events = list(events)
        self.prior = list(prior)
        self.periods: list[tuple] = []
        self.results: list[tuple] = []

    def list_rating_subscriptions(self, tenant_id):
        return self.subscriptions

    def list_usage_events(self, tenant_id, period_start, period_end):
        return self.events

    def list_prior_rollovers(self, tenant_id, before):
        return self.prior

    def upsert_rating_period(self, period_id, tenant_id, period_start, period_end) -> None:
        self.periods.append((period_id, tenant_id, period_start, period_end))

    def upsert_rating_result(
        self, result_id, period_id, subscription_id, rating, rollover_units, created_at
    ) -> None:
        self.results.append(
            (result_id, period_id, subscription_id, rating, rollover_units, created_at)
        )

    def find_rating_results(self, tenant_id, period_start):
        return [
            RatingResultRow(
                rating.used_units,
                rating.quota_units,
                rollover,
                rating.billable_units,
                rating.overage_amount,
            )
            for _id, _period, _sub, rating, rollover, _created in self.results
        ]


@pytest.mark.rule("RATING-009")
def test_finalize_upserts_period_with_legacy_md5_id() -> None:
    repository = FakeRatingRepository([subscription()], [event(260)])
    finalize_rating(repository, TENANT, FEB_START, FEB_END)
    period_id = UUID("27cdd7d2-32b3-afc0-922c-e9858e767b6d")
    assert rating_period_id(TENANT, FEB_START) == period_id
    assert repository.periods == [(period_id, TENANT, FEB_START, FEB_END)]
    assert repository.results[0][2] == UUID("20000000-0000-0000-0000-000000000001")


@pytest.mark.rule("RATING-010")
def test_finalize_stores_unused_quota_as_rollover() -> None:
    prior = [PriorRollover(date(2025, 11, 1), 100), PriorRollover(date(2026, 1, 1), 100)]
    repository = FakeRatingRepository([subscription()], [event(260)], prior)
    rows = finalize_rating(repository, TENANT, FEB_START, FEB_END)
    assert rows == [RatingResultRow(260, 100, 0, 0, Decimal("0.00"))]
    result_id, period_id, _sub, rating, _rollover, created_at = repository.results[0]
    assert rating.rollover_units == 200
    assert result_id == legacy_md5_uuid(str(period_id))
    assert created_at == datetime(2026, 2, 28, tzinfo=UTC)


@pytest.mark.rule("RATING-010")
def test_finalize_stores_remaining_quota_when_under_included() -> None:
    repository = FakeRatingRepository([subscription()], [event(40)])
    rows = finalize_rating(repository, TENANT, FEB_START, FEB_END)
    assert rows[0].rollover_units == 60
    assert repository.results[0][5] == datetime(2026, 2, 28, tzinfo=UTC)
