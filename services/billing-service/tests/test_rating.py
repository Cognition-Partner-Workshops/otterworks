from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID

import pytest

from app.domain import (
    PriorRollover,
    RatingResultRow,
    RatingSubscription,
    UsageEvent,
    available_rollover,
    finalize_rating,
    rate_usage,
    rating_period_id,
    rating_result_id,
    select_rating_subscription,
    subtract_months,
    usage_summary,
    used_units,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
TENANT_TWO = UUID("00000000-0000-0000-0000-000000000002")
STARTER_PLAN = UUID("10000000-0000-0000-0000-000000000001")
GROWTH_PLAN = UUID("10000000-0000-0000-0000-000000000002")
SCALE_PLAN = UUID("10000000-0000-0000-0000-000000000003")
STARTER_SUB = UUID("20000000-0000-0000-0000-000000000001")
GROWTH_SUB = UUID("20000000-0000-0000-0000-000000000002")

FEB = (date(2026, 2, 1), date(2026, 2, 28))

PERIOD_ID = UUID("27cdd7d2-32b3-afc0-922c-e9858e767b6d")
RESULT_ID = UUID("175fe5b7-8f91-1c3a-8586-1ef5c455fc9a")


def subscription(
    plan_id: UUID = STARTER_PLAN,
    included_units: int = 100,
    overage_rate: str = "0.055",
    starts_on: date = date(2026, 1, 1),
    ends_on: date | None = None,
    status: str = "active",
    suspended_on: date | None = None,
    subscription_id: UUID = STARTER_SUB,
) -> RatingSubscription:
    return RatingSubscription(
        subscription_id=subscription_id,
        plan_id=plan_id,
        starts_on=starts_on,
        ends_on=ends_on,
        status=status,
        suspended_on=suspended_on,
        included_units=included_units,
        overage_rate=Decimal(overage_rate),
    )


class FakeRatingRepository:
    def __init__(
        self,
        subscriptions: list[RatingSubscription],
        events: list[UsageEvent],
        prior: list[PriorRollover],
    ) -> None:
        self.subscriptions = subscriptions
        self.events = events
        self.prior = prior
        self.periods: dict[tuple[UUID, date], tuple[UUID, date]] = {}
        self.results: dict[UUID, RatingResultRow] = {}
        self.upserted_period_id: UUID | None = None

    def list_rating_subscriptions(self, tenant_id: UUID) -> list[RatingSubscription]:
        return self.subscriptions

    def list_usage_events(self, tenant_id: UUID) -> list[UsageEvent]:
        return self.events

    def list_prior_rollovers(self, tenant_id: UUID) -> list[PriorRollover]:
        return self.prior

    def upsert_rating_period(
        self,
        period_id: UUID,
        tenant_id: UUID,
        period_start: date,
        period_end: date,
    ) -> None:
        self.upserted_period_id = period_id
        key = (tenant_id, period_start)
        if key in self.periods:
            kept_id, _ = self.periods[key]
            self.periods[key] = (kept_id, period_end)
        else:
            self.periods[key] = (period_id, period_end)

    def upsert_rating_result(self, row: RatingResultRow) -> None:
        existing = self.results.get(row.result_id)
        if existing is None:
            self.results[row.result_id] = row
        else:
            self.results[row.result_id] = RatingResultRow(
                result_id=existing.result_id,
                period_id=existing.period_id,
                subscription_id=existing.subscription_id,
                used_units=row.used_units,
                quota_units=existing.quota_units,
                rollover_units=row.rollover_units,
                billable_units=row.billable_units,
                overage_amount=row.overage_amount,
                created_at=existing.created_at,
            )

    def find_rating_results(
        self, tenant_id: UUID, period_start: date
    ) -> list[RatingResultRow]:
        key = (tenant_id, period_start)
        if key not in self.periods:
            return []
        period_id, _ = self.periods[key]
        return [
            row for row in self.results.values() if row.period_id == period_id
        ]


@pytest.mark.rule("RATING-001")
def test_select_rating_subscription_latest_overlap_wins() -> None:
    older = subscription(starts_on=date(2025, 1, 1), ends_on=date(2026, 12, 31))
    newer = subscription(
        starts_on=date(2026, 1, 1),
        subscription_id=UUID("20000000-0000-0000-0000-000000000099"),
    )
    chosen = select_rating_subscription([older, newer], *FEB)
    assert chosen is newer


@pytest.mark.rule("RATING-001")
def test_select_rating_subscription_inclusive_ends() -> None:
    ends_on_start = subscription(starts_on=date(2025, 6, 1), ends_on=date(2026, 2, 1))
    chosen = select_rating_subscription([ends_on_start], *FEB)
    assert chosen is ends_on_start


@pytest.mark.rule("RATING-001")
def test_select_rating_subscription_excludes_ended_before_period() -> None:
    ended = subscription(starts_on=date(2025, 6, 1), ends_on=date(2026, 1, 31))
    assert select_rating_subscription([ended], *FEB) is None
    assert select_rating_subscription([], *FEB) is None


@pytest.mark.rule("RATING-002")
def test_used_units_inclusive_boundaries() -> None:
    events = [
        UsageEvent(date(2026, 1, 31), 50, "api"),
        UsageEvent(date(2026, 2, 1), 10, "api"),
        UsageEvent(date(2026, 2, 28), 20, "storage"),
        UsageEvent(date(2026, 3, 1), 50, "api"),
    ]
    assert used_units(events, *FEB) == 30
    assert used_units([], *FEB) == 0


@pytest.mark.rule("RATING-003")
def test_available_rollover_window_and_cap() -> None:
    prior = [
        PriorRollover(date(2025, 11, 1), 100),
        PriorRollover(date(2025, 12, 1), 100),
        PriorRollover(date(2026, 1, 1), 100),
    ]
    assert available_rollover(prior, date(2026, 2, 1), 100) == 200


@pytest.mark.rule("RATING-003")
def test_available_rollover_window_bounds() -> None:
    prior = [
        PriorRollover(date(2025, 10, 1), 100),  # before lookback: excluded
        PriorRollover(date(2025, 11, 1), 100),  # inclusive lower bound: counts
        PriorRollover(date(2026, 2, 1), 100),  # current period: excluded
    ]
    assert available_rollover(prior, date(2026, 2, 1), 500) == 100


@pytest.mark.rule("RATING-003")
def test_subtract_months_pg_semantics() -> None:
    assert subtract_months(date(2026, 5, 31), 3) == date(2026, 2, 28)
    assert subtract_months(date(2026, 2, 1), 3) == date(2025, 11, 1)


@pytest.mark.rule("RATING-004")
def test_billable_units_floor() -> None:
    sub = subscription()
    rating = rate_usage(TENANT, *FEB, sub, [UsageEvent(date(2026, 2, 10), 260, "api")], [])
    assert rating.billable_units == 160
    rolled = [PriorRollover(date(2026, 1, 1), 200)]
    rating = rate_usage(TENANT, *FEB, sub, [UsageEvent(date(2026, 2, 10), 260, "api")], rolled)
    assert rating.rollover_units == 200
    assert rating.billable_units == 0


@pytest.mark.rule("RATING-005")
def test_tier_split() -> None:
    sub = subscription(included_units=0)
    for billable, first, second in ((101, 101, 0), (102, 101, 1), (201, 101, 100)):
        rating = rate_usage(
            TENANT, *FEB, sub, [UsageEvent(date(2026, 2, 10), billable, "api")], []
        )
        assert (rating.first_tier_units, rating.second_tier_units) == (first, second)


@pytest.mark.rule("RATING-006")
def test_overage_amount_rounded_once_half_up() -> None:
    starter = subscription()
    rating = rate_usage(
        TENANT, *FEB, starter, [UsageEvent(date(2026, 2, 28), 201, "api")], []
    )
    assert rating.billable_units == 101
    assert rating.overage_amount == Decimal("5.56")

    scale = subscription(plan_id=SCALE_PLAN, included_units=2000, overage_rate="0.020")
    rating = rate_usage(
        TENANT, *FEB, scale, [UsageEvent(date(2026, 2, 10), 2201, "compute")], []
    )
    assert rating.billable_units == 201
    assert rating.overage_amount == Decimal("5.02")

    rating = rate_usage(TENANT, *FEB, starter, [], [])
    assert rating.overage_amount == Decimal("0.00")


@pytest.mark.rule("RATING-007")
def test_suspension_proration_transcript_case() -> None:
    # tenant 2: GROWTH 500/0.035, 700 used, suspended 2026-02-15
    growth = subscription(
        plan_id=GROWTH_PLAN,
        subscription_id=GROWTH_SUB,
        included_units=500,
        overage_rate="0.035",
        status="suspended",
        suspended_on=date(2026, 2, 15),
    )
    rating = rate_usage(
        TENANT_TWO, *FEB, growth, [UsageEvent(date(2026, 2, 10), 700, "api")], []
    )
    # billable 200, factor = (28-15+1)/28 = 14/28 -> 100; amount 8.73 * 0.5 = 4.365 -> 4.37
    assert rating.billable_units == 100
    assert rating.overage_amount == Decimal("4.37")
    assert (rating.first_tier_units, rating.second_tier_units) == (101, 99)


@pytest.mark.rule("RATING-007")
def test_suspension_proration_asymmetric_counts_suspended_portion() -> None:
    # suspended 2026-02-22: suspended days Feb 22..28 = 7, factor 7/28 = 1/4
    # billable 200 -> 50; amount 8.73 * 1/4 = 2.1825 -> 2.18
    growth = subscription(
        plan_id=GROWTH_PLAN,
        subscription_id=GROWTH_SUB,
        included_units=500,
        overage_rate="0.035",
        status="suspended",
        suspended_on=date(2026, 2, 22),
    )
    rating = rate_usage(
        TENANT_TWO, *FEB, growth, [UsageEvent(date(2026, 2, 10), 700, "api")], []
    )
    assert rating.billable_units == 50
    assert rating.overage_amount == Decimal("2.18")


@pytest.mark.rule("RATING-007")
def test_no_proration_when_not_suspended_in_period() -> None:
    active_but_dated = subscription(
        included_units=500,
        overage_rate="0.035",
        status="active",
        suspended_on=date(2026, 2, 15),
    )
    events = [UsageEvent(date(2026, 2, 10), 700, "api")]
    rating = rate_usage(TENANT_TWO, *FEB, active_but_dated, events, [])
    assert rating.billable_units == 200
    assert rating.overage_amount == Decimal("8.73")

    out_of_period = subscription(
        included_units=500,
        overage_rate="0.035",
        status="suspended",
        suspended_on=date(2026, 3, 5),
    )
    rating = rate_usage(TENANT_TWO, *FEB, out_of_period, events, [])
    assert rating.billable_units == 200
    assert rating.overage_amount == Decimal("8.73")


@pytest.mark.rule("RATING-008")
def test_usage_summary_groups_by_kind() -> None:
    events = [
        UsageEvent(date(2026, 2, 5), 20, "api"),
        UsageEvent(date(2026, 2, 6), 30, "storage"),
        UsageEvent(date(2026, 3, 1), 10, "compute"),
    ]
    rows = usage_summary(events, *FEB)
    assert [(r.kind, r.event_count, r.units) for r in rows] == [
        ("api", 1, 20),
        ("storage", 1, 30),
    ]


@pytest.mark.rule("RATING-009")
def test_deterministic_ids_match_postgres() -> None:
    assert rating_period_id(TENANT, date(2026, 2, 1)) == PERIOD_ID
    assert rating_result_id(PERIOD_ID) == RESULT_ID


@pytest.mark.rule("RATING-009")
def test_finalize_upserts_computed_period_id() -> None:
    repo = FakeRatingRepository([subscription()], [], [])
    finalize_rating(repo, TENANT, *FEB)
    assert repo.upserted_period_id == PERIOD_ID


@pytest.mark.rule("RATING-010")
def test_finalize_stores_unused_quota_as_rollover() -> None:
    prior = [
        PriorRollover(date(2025, 11, 1), 100),
        PriorRollover(date(2025, 12, 1), 100),
        PriorRollover(date(2026, 1, 1), 100),
    ]
    repo = FakeRatingRepository(
        [subscription()],
        [UsageEvent(date(2026, 2, 10), 260, "api")],
        prior,
    )
    rows = finalize_rating(repo, TENANT, *FEB)
    assert len(rows) == 1
    row = rows[0]
    assert row.result_id == RESULT_ID
    assert row.period_id == PERIOD_ID
    assert row.subscription_id == STARTER_SUB
    assert row.used_units == 260
    assert row.quota_units == 100
    assert row.rollover_units == 0
    assert row.billable_units == 0
    assert row.overage_amount == Decimal("0.00")
    assert row.created_at == datetime.combine(date(2026, 2, 28), time(), tzinfo=UTC)


@pytest.mark.rule("RATING-010")
def test_refinalize_updates_only_rated_fields() -> None:
    events = [UsageEvent(date(2026, 2, 10), 260, "api")]
    repo = FakeRatingRepository([subscription()], events, [])
    finalize_rating(repo, TENANT, *FEB)
    first = repo.results[RESULT_ID]

    repo.events = [UsageEvent(date(2026, 2, 10), 310, "api")]
    finalize_rating(repo, TENANT, *FEB)
    second = repo.results[RESULT_ID]

    assert second.period_id == first.period_id
    assert second.subscription_id == first.subscription_id
    assert second.quota_units == first.quota_units
    assert second.created_at == first.created_at
    assert second.used_units == 310
    assert second.rollover_units == 0
    # billable 210 -> 101*0.055 + 109*0.055*1.5 = 5.555 + 8.9925 = 14.5475 -> 14.55
    assert second.billable_units == 210
    assert second.overage_amount == Decimal("14.55")
