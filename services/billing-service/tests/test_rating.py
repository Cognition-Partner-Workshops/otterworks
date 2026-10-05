from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.domain import (
    NoSubscriptionError,
    PlanRow,
    PriorRatingRow,
    RatingRow,
    StoredRatingResult,
    SubscriptionRow,
    UsageEventRow,
    finalize_rating,
    prior_rollover,
    rate_period,
    rate_usage,
    rating_period_id,
    rating_result_id,
    round2,
    select_rating_subscription,
    summarize_usage,
    used_units,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
PLAN_STARTER = UUID("10000000-0000-0000-0000-000000000001")
PLAN_GROWTH = UUID("10000000-0000-0000-0000-000000000002")
PLAN_SCALE = UUID("10000000-0000-0000-0000-000000000003")
SUBSCRIPTION = UUID("20000000-0000-0000-0000-000000000001")
START = date(2026, 2, 1)
END = date(2026, 2, 28)

PLANS = {
    PLAN_STARTER: PlanRow(
        PLAN_STARTER, "STARTER", "starter", Decimal("49.00"), 100, Decimal("0.055000"), True
    ),
    PLAN_GROWTH: PlanRow(
        PLAN_GROWTH, "GROWTH", "growth", Decimal("149.00"), 500, Decimal("0.035000"), True
    ),
    PLAN_SCALE: PlanRow(
        PLAN_SCALE, "SCALE", "scale", Decimal("499.00"), 2000, Decimal("0.020000"), True
    ),
}


class FakeRepository:
    def __init__(
        self,
        subscriptions: list[SubscriptionRow] | None = None,
        events: list[UsageEventRow] | None = None,
        prior: list[PriorRatingRow] | None = None,
    ) -> None:
        self.subscriptions = subscriptions or []
        self.events = events or []
        self.prior = prior or []
        self.periods: dict[tuple[UUID, date], tuple[UUID, date]] = {}
        self.results: dict[UUID, StoredRatingResult] = {}
        self.period_result_ids: dict[tuple[UUID, date], UUID] = {}
        self.period_upserts: list[tuple[UUID, UUID, date, date]] = []
        self.result_upserts: list[
            tuple[UUID, UUID, UUID, int, int | None, int, int, Decimal | None, datetime]
        ] = []

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        return [row for row in self.subscriptions if row.tenant_id == tenant_id]

    def get_plan(self, plan_id: UUID) -> PlanRow | None:
        return PLANS.get(plan_id)

    def list_usage_events(self, tenant_id: UUID) -> list[UsageEventRow]:
        return [event for event in self.events if event.tenant_id == tenant_id]

    def list_prior_ratings(self, tenant_id: UUID) -> list[PriorRatingRow]:
        del tenant_id
        return list(self.prior)

    def upsert_rating_period(
        self, period_id: UUID, tenant_id: UUID, start: date, end: date
    ) -> None:
        self.period_upserts.append((period_id, tenant_id, start, end))
        self.periods[(tenant_id, start)] = period_id, end

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
    ) -> None:
        self.result_upserts.append(
            (
                result_id,
                period_id,
                subscription_id,
                used_units,
                quota_units,
                rollover_units,
                billable_units,
                overage_amount,
                created_at,
            )
        )
        existing = self.results.get(result_id)
        self.results[result_id] = StoredRatingResult(
            used_units=used_units,
            quota_units=(
                existing.quota_units
                if existing is not None
                else quota_units if quota_units is not None else 0
            ),
            rollover_units=rollover_units,
            billable_units=billable_units,
            overage_amount=overage_amount if overage_amount is not None else Decimal(0),
        )
        for key, (stored_period_id, _end) in self.periods.items():
            if stored_period_id == period_id:
                self.period_result_ids[key] = result_id

    def get_rating_result(self, tenant_id: UUID, start: date) -> StoredRatingResult:
        return self.results[self.period_result_ids[(tenant_id, start)]]


def subscription(
    *,
    subscription_id: UUID = SUBSCRIPTION,
    tenant_id: UUID = TENANT,
    plan_id: UUID = PLAN_STARTER,
    starts_on: date = date(2026, 1, 1),
    ends_on: date | None = None,
    status: str = "active",
    suspended_on: date | None = None,
) -> SubscriptionRow:
    return SubscriptionRow(
        subscription_id, tenant_id, plan_id, starts_on, ends_on, status, suspended_on
    )


def event(
    units: int,
    kind: str = "api",
    occurred_at: datetime = datetime(2026, 2, 10, 10, tzinfo=UTC),
    tenant_id: UUID = TENANT,
) -> UsageEventRow:
    return UsageEventRow(tenant_id, occurred_at, units, kind)


def rate_for_seed_tenant(tenant_number: int) -> RatingRow:
    tenant_id = UUID(f"00000000-0000-0000-0000-{tenant_number:012d}")
    plan_id = {
        2: PLAN_GROWTH,
        3: PLAN_SCALE,
        5: PLAN_GROWTH,
    }.get(tenant_number, PLAN_STARTER)
    status = "suspended" if tenant_number == 2 else "active"
    sub = subscription(
        tenant_id=tenant_id,
        plan_id=plan_id,
        status=status,
        suspended_on=date(2026, 2, 15) if status == "suspended" else None,
    )
    quantities = {2: 700, 3: 2201, 6: 201, 7: 260, 8: 202}
    return rate_period(
        FakeRepository(
            [sub],
            [event(quantities[tenant_number], tenant_id=tenant_id)],
        ),
        tenant_id,
        START,
        END,
    )


@pytest.mark.rule("RATING-001")
def test_rating_selects_latest_overlapping_subscription_and_matches_tenant_seven() -> None:
    earlier = subscription(starts_on=date(2026, 1, 1))
    later = subscription(
        subscription_id=UUID("20000000-0000-0000-0000-000000000002"),
        starts_on=date(2026, 2, 10),
        status="cancelled",
    )
    row = rate_period(
        FakeRepository(
            [earlier, later],
            [event(260)],
        ),
        TENANT,
        START,
        END,
    )
    assert row.quota_units == 100
    assert row.used_units == 260
    assert row.billable_units == 160
    assert select_rating_subscription([earlier, later], START, END) == later
    tenant_seven = rate_for_seed_tenant(7)
    assert (tenant_seven.used_units, tenant_seven.rollover_units, tenant_seven.billable_units) == (
        260,
        0,
        160,
    )


@pytest.mark.rule("RATING-001")
def test_equal_subscription_start_dates_break_ties_by_smallest_string_id() -> None:
    highest = subscription(subscription_id=UUID("f0000000-0000-0000-0000-000000000001"))
    lowest = subscription(subscription_id=UUID("10000000-0000-0000-0000-000000000001"))
    assert select_rating_subscription([highest, lowest], START, END) == lowest


@pytest.mark.rule("RATING-001")
def test_missing_subscription_keeps_null_quota_and_amount_with_zero_units() -> None:
    row = rate_period(FakeRepository(events=[event(260)]), TENANT, START, END)
    assert row.quota_units is None
    assert row.overage_amount is None
    assert (row.used_units, row.rollover_units, row.billable_units) == (260, 0, 0)
    assert (row.first_tier_units, row.second_tier_units) == (0, 0)


@pytest.mark.rule("RATING-002")
def test_used_units_includes_utc_calendar_date_bounds() -> None:
    events = [
        event(3, occurred_at=datetime(2026, 2, 1, 0, 0, tzinfo=UTC)),
        event(5, occurred_at=datetime(2026, 2, 28, 23, 59, tzinfo=UTC)),
        event(7, occurred_at=datetime(2026, 3, 1, 0, 0, tzinfo=UTC)),
        event(11, occurred_at=datetime.fromisoformat("2026-02-28T23:30:00-05:00")),
    ]
    assert used_units(events, START, END) == 8
    assert used_units([], START, END) == 0


@pytest.mark.rule("RATING-003")
def test_prior_rollover_has_inclusive_three_month_bound_and_clamped_month_end() -> None:
    rows = [
        PriorRatingRow(date(2025, 11, 27), 3),
        PriorRatingRow(date(2025, 11, 28), 5),
        PriorRatingRow(date(2026, 5, 31), 7),
    ]
    assert prior_rollover(rows, date(2026, 2, 28), None) == 5
    may_rows = [
        PriorRatingRow(date(2026, 2, 27), 2),
        PriorRatingRow(date(2026, 2, 28), 11),
        PriorRatingRow(date(2026, 5, 31), 13),
    ]
    assert prior_rollover(may_rows, date(2026, 5, 31), None) == 11


@pytest.mark.rule("RATING-003")
def test_seed_tenant_one_rollover_is_capped_at_two_quotas() -> None:
    row = rate_period(
        FakeRepository(
            [subscription()],
            [event(260)],
            [
                PriorRatingRow(date(2025, 11, 1), 100),
                PriorRatingRow(date(2025, 12, 1), 100),
                PriorRatingRow(date(2026, 1, 1), 100),
            ],
        ),
        TENANT,
        START,
        END,
    )
    assert row.rollover_units == 200
    assert row.billable_units == 0
    assert row.overage_amount == Decimal("0.00")


@pytest.mark.rule("RATING-004")
def test_billable_units_subtract_included_units_and_rollover_before_flooring() -> None:
    row = rate_usage(None, PLANS[PLAN_STARTER], 260, 200, TENANT, START, END)
    assert row.billable_units == 0
    assert rate_usage(None, PLANS[PLAN_STARTER], 260, 0, TENANT, START, END).billable_units == 160


@pytest.mark.rule("RATING-005")
def test_tiering_uses_literal_101_boundary() -> None:
    at_boundary = rate_for_seed_tenant(6)
    over_boundary = rate_for_seed_tenant(8)
    assert (at_boundary.billable_units, at_boundary.first_tier_units) == (101, 101)
    assert (over_boundary.first_tier_units, over_boundary.second_tier_units) == (101, 1)


@pytest.mark.rule("RATING-006")
def test_overage_uses_half_up_rounding_without_floats() -> None:
    starter = replace(PLANS[PLAN_STARTER], included_units=0)
    assert rate_usage(None, starter, 101, 0, TENANT, START, END).overage_amount == Decimal(
        "5.56"
    )
    rate = replace(starter, overage_rate=Decimal("0.043650"))
    assert rate_usage(None, rate, 100, 0, TENANT, START, END).overage_amount == Decimal(
        "4.37"
    )
    assert round2(Decimal("5.555")) == Decimal("5.56")
    assert round2(Decimal("4.365")) == Decimal("4.37")


@pytest.mark.rule("RATING-006")
def test_seed_overage_amounts_match_tier_and_scale_transcripts() -> None:
    two = rate_for_seed_tenant(2)
    six = rate_for_seed_tenant(6)
    three = rate_for_seed_tenant(3)
    assert (two.billable_units, two.overage_amount) == (100, Decimal("4.37"))
    assert (six.overage_amount, six.first_tier_units) == (Decimal("5.56"), 101)
    assert (three.billable_units, three.first_tier_units, three.second_tier_units) == (
        201,
        101,
        100,
    )
    assert three.overage_amount == Decimal("5.02")


@pytest.mark.rule("RATING-007")
def test_suspension_prorates_suspended_days_but_not_tiers() -> None:
    suspended = subscription(
        plan_id=PLAN_GROWTH,
        status="suspended",
        suspended_on=date(2026, 2, 21),
    )
    row = rate_usage(suspended, PLANS[PLAN_GROWTH], 700, 0, TENANT, START, END)
    assert (row.billable_units, row.first_tier_units, row.second_tier_units) == (57, 101, 99)
    assert row.overage_amount == Decimal("2.49")


@pytest.mark.rule("RATING-007")
def test_suspension_outside_period_or_active_status_does_not_prorate() -> None:
    plan = PLANS[PLAN_GROWTH]
    before = subscription(plan_id=PLAN_GROWTH, status="suspended", suspended_on=date(2026, 1, 31))
    active = subscription(plan_id=PLAN_GROWTH, status="active", suspended_on=date(2026, 2, 21))
    for item in (before, active):
        row = rate_usage(item, plan, 700, 0, TENANT, START, END)
        assert (row.billable_units, row.overage_amount) == (200, Decimal("8.73"))


@pytest.mark.rule("RATING-008")
def test_usage_summary_groups_sorted_kinds_and_omits_empty_groups() -> None:
    tenant_four = UUID("00000000-0000-0000-0000-000000000004")
    result = summarize_usage(
        [
            event(30, "storage", tenant_id=tenant_four),
            event(20, "api", tenant_id=tenant_four),
            event(
                9,
                "compute",
                occurred_at=datetime(2026, 3, 1, tzinfo=UTC),
                tenant_id=tenant_four,
            ),
        ],
        START,
        END,
    )
    assert [(row.kind, row.event_count, row.units) for row in result] == [
        ("api", 1, 20),
        ("storage", 1, 30),
    ]


@pytest.mark.rule("RATING-009")
def test_finalize_rating_upserts_period_using_deterministic_md5_id() -> None:
    repository = FakeRepository([subscription()], [event(260)])
    stored = finalize_rating(repository, TENANT, START, END)
    period_id = UUID("27cdd7d2-32b3-afc0-922c-e9858e767b6d")
    assert rating_period_id(TENANT, START) == period_id
    assert repository.period_upserts == [(period_id, TENANT, START, END)]
    assert rating_result_id(period_id) == UUID("175fe5b7-8f91-1c3a-8586-1ef5c455fc9a")
    assert stored.quota_units == 100


@pytest.mark.rule("RATING-009")
def test_finalize_rerun_updates_period_end_and_result_fields_only() -> None:
    repository = FakeRepository([subscription()], [event(40)])
    first = finalize_rating(repository, TENANT, START, END)
    assert first == StoredRatingResult(40, 100, 60, 0, Decimal("0.00"))
    repository.events = [event(260)]
    changed_end = date(2026, 3, 1)
    second = finalize_rating(repository, TENANT, START, changed_end)
    assert repository.periods[(TENANT, START)] == (rating_period_id(TENANT, START), changed_end)
    assert second == StoredRatingResult(260, 100, 0, 160, Decimal("10.42"))
    assert repository.result_upserts[1][-1] == datetime(2026, 3, 1, tzinfo=UTC)


@pytest.mark.rule("RATING-010")
def test_finalize_persists_stored_rollover_and_reads_result_back() -> None:
    repository = FakeRepository(
        [subscription()],
        [event(260)],
        [
            PriorRatingRow(date(2025, 11, 1), 100),
            PriorRatingRow(date(2025, 12, 1), 100),
            PriorRatingRow(date(2026, 1, 1), 100),
        ],
    )
    stored = finalize_rating(repository, TENANT, START, END)
    assert stored == StoredRatingResult(260, 100, 0, 0, Decimal("0.00"))
    assert repository.result_upserts[0][5] == 0
    assert repository.result_upserts[0][-1] == datetime(2026, 2, 28, tzinfo=UTC)


@pytest.mark.rule("RATING-010")
def test_finalize_without_subscription_raises_domain_error_before_writes() -> None:
    repository = FakeRepository()
    with pytest.raises(NoSubscriptionError):
        finalize_rating(repository, TENANT, START, END)
    assert repository.period_upserts == []
    assert repository.result_upserts == []


def test_finalize_api_maps_missing_subscription_to_422(monkeypatch) -> None:
    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def raise_no_subscription(*_args: object) -> StoredRatingResult:
        raise NoSubscriptionError("no subscription overlaps the requested period")

    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "finalize_rating", raise_no_subscription)
    with TestClient(main.app) as client:
        response = client.post(
            f"/api/tenants/{TENANT}/rating/finalize",
            json={"period_start": START.isoformat(), "period_end": END.isoformat()},
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "no subscription overlaps the requested period"
