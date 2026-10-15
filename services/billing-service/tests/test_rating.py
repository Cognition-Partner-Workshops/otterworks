from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from app.domain import (
    InvalidPeriodError,
    NoSubscriptionError,
    PlanRow,
    RatingResultRow,
    SubscriptionRow,
    UsageSummaryRow,
    finalize_rating,
    legacy_uuid,
    months_before,
    usage_rating,
    usage_summary,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
STARTER = UUID("10000000-0000-0000-0000-000000000001")
SUBSCRIPTION = UUID("20000000-0000-0000-0000-000000000001")
FEB_START, FEB_END = date(2026, 2, 1), date(2026, 2, 28)
STARTER_PLAN = PlanRow(STARTER, "STARTER", "starter", Decimal("49"), 100, Decimal("0.055"), True)


class FakeRatingRepository:
    def __init__(
        self,
        used: int = 0,
        prior_rollover: int = 0,
        subscription: SubscriptionRow | None = None,
        by_kind: list[UsageSummaryRow] | None = None,
    ) -> None:
        self.used = used
        self.prior_rollover = prior_rollover
        self.subscription = subscription or SubscriptionRow(
            SUBSCRIPTION, TENANT, STARTER, date(2026, 1, 1), None, "active", None
        )
        self.by_kind = by_kind or []
        self.windows: list[tuple[date, date]] = []
        self.periods: dict[tuple[UUID, date], tuple[UUID, date]] = {}
        self.results: dict[UUID, tuple[RatingResultRow, date]] = {}  # keyed by period id

    def list_plans(self) -> list[PlanRow]:
        return [STARTER_PLAN]

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        return [self.subscription]

    def sum_usage_units(self, tenant_id: UUID, period_start: date, period_end: date) -> int:
        return self.used

    def usage_by_kind(
        self, tenant_id: UUID, period_start: date, period_end: date
    ) -> list[UsageSummaryRow]:
        return list(self.by_kind)

    def sum_prior_rollover_units(
        self, tenant_id: UUID, window_start: date, period_start: date
    ) -> int:
        self.windows.append((window_start, period_start))
        return self.prior_rollover

    def upsert_rating_period(
        self, tenant_id: UUID, period_id: UUID, period_start: date, period_end: date
    ) -> UUID:
        existing_id, _ = self.periods.get((tenant_id, period_start), (period_id, period_end))
        self.periods[(tenant_id, period_start)] = (existing_id, period_end)
        return existing_id

    def upsert_rating_result(self, result: RatingResultRow, created_at: date) -> RatingResultRow:
        if result.period_id in self.results:
            first, first_created = self.results[result.period_id]
            result = replace(
                first,
                used_units=result.used_units,
                rollover_units=result.rollover_units,
                billable_units=result.billable_units,
                overage_amount=result.overage_amount,
            )
            created_at = first_created
        self.results[result.period_id] = (result, created_at)
        return result


@pytest.mark.rule("RATING-001")
def test_used_units_come_from_the_period_sum_and_zero_rollover_bills_the_rest() -> None:
    row = usage_rating(FakeRatingRepository(used=260), TENANT, FEB_START, FEB_END)
    assert (row.used_units, row.quota_units, row.rollover_units) == (260, 100, 0)
    assert row.billable_units == 160


@pytest.mark.rule("RATING-002")
def test_rollover_is_the_three_month_window_capped_at_twice_the_quota() -> None:
    repository = FakeRatingRepository(used=260, prior_rollover=300)
    row = usage_rating(repository, TENANT, FEB_START, FEB_END)
    assert repository.windows == [(date(2025, 11, 1), FEB_START)]
    assert (row.rollover_units, row.billable_units, row.overage_amount) == (200, 0, Decimal("0.00"))


@pytest.mark.rule("RATING-002")
def test_rollover_window_follows_postgresql_month_arithmetic() -> None:
    assert months_before(date(2026, 5, 31), 3) == date(2026, 2, 28)
    assert months_before(date(2026, 1, 15), 3) == date(2025, 10, 15)


@pytest.mark.rule("RATING-003")
@pytest.mark.parametrize(
    ("used", "first", "second", "amount"),
    [
        (700, 101, 499, Decimal("46.72")),  # 101*0.055 + 499*0.055*1.5 = 5.555 + 41.1675
        (201, 101, 0, Decimal("5.56")),  # 5.555 rounds half up to the cent
        (202, 101, 1, Decimal("5.64")),  # 5.555 + 0.0825 = 5.6375
        (2201, 101, 2000, Decimal("170.56")),  # 5.555 + 165
    ],
)
def test_tiers_split_at_101_units_and_round_to_cents(
    used: int, first: int, second: int, amount: Decimal
) -> None:
    row = usage_rating(FakeRatingRepository(used=used), TENANT, FEB_START, FEB_END)
    assert (row.first_tier_units, row.second_tier_units, row.overage_amount) == (
        first,
        second,
        amount,
    )


@pytest.mark.rule("RATING-003")
def test_suspension_inside_the_period_prorates_units_and_amount() -> None:
    suspended = SubscriptionRow(
        SUBSCRIPTION, TENANT, STARTER, date(2026, 1, 1), None, "suspended", date(2026, 2, 15)
    )
    row = usage_rating(
        FakeRatingRepository(used=260, subscription=suspended), TENANT, FEB_START, FEB_END
    )
    # 14 of 28 days remain after the suspension date: 160 * 0.5 and 10.42 * 0.5
    assert (row.billable_units, row.overage_amount) == (80, Decimal("5.21"))
    assert (row.first_tier_units, row.second_tier_units) == (101, 59)


def test_rating_requires_a_subscription_covering_the_period() -> None:
    ended = SubscriptionRow(
        SUBSCRIPTION, TENANT, STARTER, date(2025, 1, 1), date(2025, 12, 31), "active", None
    )
    with pytest.raises(NoSubscriptionError):
        usage_rating(FakeRatingRepository(subscription=ended), TENANT, FEB_START, FEB_END)


@pytest.mark.rule("RATING-004")
def test_usage_summary_is_ordered_by_kind() -> None:
    rows = [UsageSummaryRow("storage", 1, 30), UsageSummaryRow("api", 1, 20)]
    summary = usage_summary(FakeRatingRepository(by_kind=rows), TENANT, FEB_START, FEB_END)
    assert [(row.kind, row.units) for row in summary] == [("api", 20), ("storage", 30)]


@pytest.mark.rule("RATING-005")
def test_finalize_uses_legacy_md5_ids_and_stores_the_unused_quota_as_rollover() -> None:
    repository = FakeRatingRepository(used=260, prior_rollover=300)
    result = finalize_rating(repository, TENANT, FEB_START, FEB_END)
    # md5('00000000-...-0001' || '2026-02-01')::uuid and md5(period_id::text)::uuid
    assert result.period_id == legacy_uuid(TENANT, "2026-02-01")
    assert result.period_id == UUID("27cdd7d2-32b3-afc0-922c-e9858e767b6d")
    assert result.result_id == legacy_uuid(result.period_id)
    assert (result.used_units, result.quota_units, result.rollover_units) == (260, 100, 0)
    assert (result.billable_units, result.overage_amount) == (0, Decimal("0.00"))


@pytest.mark.rule("RATING-005")
def test_finalize_is_idempotent_and_keeps_the_first_subscription_quota_and_created_at() -> None:
    repository = FakeRatingRepository(used=260)
    first = finalize_rating(repository, TENANT, FEB_START, FEB_END)
    repository.used = 400
    second = finalize_rating(repository, TENANT, FEB_START, date(2026, 2, 27))
    assert second.period_id == first.period_id and second.result_id == first.result_id
    assert repository.periods[(TENANT, FEB_START)] == (first.period_id, date(2026, 2, 27))
    stored, created_at = repository.results[first.period_id]
    assert second == stored
    assert (stored.used_units, stored.billable_units) == (400, 300)
    assert (stored.subscription_id, stored.quota_units, created_at) == (SUBSCRIPTION, 100, FEB_END)
    assert len(repository.results) == 1


@pytest.mark.rule("RATING-005")
def test_finalize_keeps_an_imported_result_identity_and_returns_the_persisted_row() -> None:
    repository = FakeRatingRepository(used=260)
    imported_period = UUID("40000000-0000-0000-0000-000000000002")
    imported_result = UUID("50000000-0000-0000-0000-000000000002")
    other_subscription = UUID("20000000-0000-0000-0000-000000000009")
    repository.periods[(TENANT, FEB_START)] = (imported_period, FEB_END)
    repository.results[imported_period] = (
        RatingResultRow(
            imported_period, imported_result, other_subscription, 0, 500, 500, 0, Decimal("0")
        ),
        date(2026, 1, 31),
    )
    result = finalize_rating(repository, TENANT, FEB_START, FEB_END)
    assert (result.period_id, result.result_id) == (imported_period, imported_result)
    # subscription and quota are the imported ones, not the ones computed for this call
    assert (result.subscription_id, result.quota_units) == (other_subscription, 500)
    assert (result.used_units, result.rollover_units, result.billable_units) == (260, 0, 160)


def test_finalize_rejects_a_period_that_ends_before_it_starts() -> None:
    repository = FakeRatingRepository(used=260)
    with pytest.raises(InvalidPeriodError):
        finalize_rating(repository, TENANT, FEB_END, FEB_START)
    assert repository.periods == {} and repository.results == {}
