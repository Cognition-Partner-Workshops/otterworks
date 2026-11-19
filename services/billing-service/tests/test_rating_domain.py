import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from app.domain import PlanRow, SubscriptionRow

TENANT = UUID(int=1)
OTHER = UUID(int=2)
PLAN = UUID(int=10)
START = date(2026, 2, 1)
END = date(2026, 2, 28)


@pytest.fixture
def rating_api():
    """Step 2 API: immutable rows, pure rating/summary, repository-backed finalize."""
    try:
        return import_module("app.rating_domain")
    except ModuleNotFoundError as exc:
        if exc.name != "app.rating_domain":
            raise
        pytest.skip("Step 2 has not implemented app.rating_domain yet")


def plan(quota=100, rate="0.055", plan_id=PLAN):
    return PlanRow(plan_id, "TEST", "starter", Decimal("49"), quota, Decimal(rate), True)


def subscription(
    starts=date(2026, 1, 1), ends=None, status="active", suspended=None, tenant=TENANT, plan_id=PLAN
):
    return SubscriptionRow(UUID(int=20), tenant, plan_id, starts, ends, status, suspended)


def event(api, units, when="2026-02-10T10:00:00+00:00", kind="api", tenant=TENANT):
    return api.UsageEventRow(tenant, datetime.fromisoformat(when), units, kind)


def rate(api, events=(), priors=(), plans=None, subscriptions=None, tz=UTC):
    return api.usage_rating(
        plans=[plan()] if plans is None else plans,
        subscriptions=[subscription()] if subscriptions is None else subscriptions,
        events=list(events),
        prior_results=list(priors),
        tenant_id=TENANT,
        period_start=START,
        period_end=END,
        session_timezone=tz,
    )


@pytest.mark.rule("RATING-001")
def test_latest_overlapping_subscription_supplies_plan_without_status_filter(rating_api):
    later_plan = UUID(int=11)
    rows = [
        subscription(),
        subscription(date(2026, 2, 28), END, "cancelled", plan_id=later_plan),
        subscription(date(2026, 3, 1)),
        subscription(ends=date(2026, 1, 31)),
        subscription(date(2026, 2, 28), tenant=OTHER),
    ]
    result = rate(
        rating_api,
        [event(rating_api, 601)],
        subscriptions=rows,
        plans=[plan(), plan(500, "0.035", later_plan)],
    )
    assert (result.quota_units, result.billable_units, result.overage_amount) == (
        500,
        101,
        Decimal("3.54"),
    )


@pytest.mark.rule("RATING-002")
@pytest.mark.parametrize("tz, expected", [(UTC, 5), (ZoneInfo("America/New_York"), 10)])
def test_usage_uses_session_dates_and_tenant(rating_api, tz, expected):
    events = [
        event(rating_api, 2, "2026-02-01T00:30:00+00:00"),
        event(rating_api, 3, "2026-02-28T23:59:59+00:00"),
        event(rating_api, 7, "2026-03-01T00:30:00+00:00"),
        event(rating_api, 999, tenant=OTHER),
    ]
    assert rate(rating_api, events, tz=tz).used_units == expected


@pytest.mark.rule("RATING-002")
@pytest.mark.rule("RATING-003")
@pytest.mark.rule("RATING-004")
def test_no_usage_or_prior_results_returns_zero_charge(rating_api):
    result = rate(rating_api)
    assert (
        result.used_units,
        result.rollover_units,
        result.billable_units,
        result.overage_amount,
    ) == (0, 0, 0, Decimal("0.00"))


@pytest.mark.rule("RATING-003")
@pytest.mark.parametrize("credits, expected", [([50, 25], 75), ([150, 150], 200)])
def test_rollover_calendar_window_and_cap(rating_api, credits, expected):
    priors = [
        rating_api.PriorRatingRow(TENANT, date(2025, 11, 1), credits[0]),
        rating_api.PriorRatingRow(TENANT, date(2026, 1, 31), credits[1]),
        rating_api.PriorRatingRow(TENANT, date(2025, 10, 31), 999),
        rating_api.PriorRatingRow(TENANT, START, 999),
        rating_api.PriorRatingRow(OTHER, date(2026, 1, 1), 999),
    ]
    assert rate(rating_api, priors=priors).rollover_units == expected


@pytest.mark.rule("RATING-004")
@pytest.mark.parametrize("used, expected", [(99, 0), (150, 0), (151, 1)])
def test_billable_subtracts_both_quota_and_rollover(rating_api, used, expected):
    prior = rating_api.PriorRatingRow(TENANT, date(2026, 1, 1), 50)
    assert rate(rating_api, [event(rating_api, used)], [prior]).billable_units == expected


@pytest.mark.rule("RATING-005")
@pytest.mark.parametrize(
    "used, first, second, amount",
    [
        (200, 100, 0, "5.50"),
        (201, 101, 0, "5.56"),
        (202, 101, 1, "5.64"),
        (301, 101, 100, "13.81"),
    ],
)
def test_101_boundary_and_half_away_rounding(rating_api, used, first, second, amount):
    result = rate(rating_api, [event(rating_api, used)])
    assert (result.first_tier_units, result.second_tier_units, result.overage_amount) == (
        first,
        second,
        Decimal(amount),
    )


@pytest.mark.rule("RATING-006")
def test_proration_rounds_amount_twice_and_keeps_original_tiers(rating_api):
    result = rate(
        rating_api,
        [event(rating_api, 700)],
        plans=[plan(500, "0.035")],
        subscriptions=[subscription(status="suspended", suspended=date(2026, 2, 15))],
    )
    assert (result.used_units, result.quota_units, result.rollover_units) == (700, 500, 0)
    assert (result.billable_units, result.overage_amount) == (100, Decimal("4.37"))
    assert (result.first_tier_units, result.second_tier_units) == (101, 99)


@pytest.mark.rule("RATING-006")
@pytest.mark.parametrize(
    "status, suspended, billable, amount",
    [
        ("active", date(2026, 2, 15), 101, "5.56"),
        ("suspended", None, 101, "5.56"),
        ("suspended", date(2026, 1, 31), 101, "5.56"),
        ("suspended", date(2026, 3, 1), 101, "5.56"),
        ("suspended", START, 101, "5.56"),
        ("suspended", date(2026, 2, 15), 51, "2.78"),
        ("suspended", END, 4, "0.20"),
    ],
)
def test_proration_guards_inclusive_days_and_integer_rounding(
    rating_api,
    status,
    suspended,
    billable,
    amount,
):
    result = rate(
        rating_api,
        [event(rating_api, 201)],
        subscriptions=[subscription(status=status, suspended=suspended)],
    )
    assert (result.billable_units, result.overage_amount) == (billable, Decimal(amount))


@pytest.mark.rule("RATING-007")
def test_summary_counts_sums_orders_and_filters(rating_api):
    events = [
        event(rating_api, 2, kind="storage"),
        event(rating_api, 3),
        event(rating_api, 4),
        event(rating_api, 999, tenant=OTHER),
        event(rating_api, 999, "2026-03-01T00:00:00+00:00"),
    ]
    rows = rating_api.usage_summary(events, TENANT, START, END, session_timezone=UTC)
    assert [(r.kind, r.event_count, r.units) for r in rows] == [("api", 2, 7), ("storage", 1, 2)]
    assert rating_api.usage_summary([], TENANT, START, END, session_timezone=UTC) == []


class RecordingRepository:
    def __init__(self, api):
        self.api = api
        self.period_writes = []
        self.result_writes = []

    def list_plans(self):
        return [plan()]

    def list_subscriptions(self, tenant_id):
        assert tenant_id == TENANT
        return [subscription()]

    def list_usage_events(self, tenant_id):
        assert tenant_id == TENANT
        return [event(self.api, 25)]

    def list_prior_rating_results(self, tenant_id):
        assert tenant_id == TENANT
        return [self.api.PriorRatingRow(TENANT, date(2026, 1, 1), 50)]

    def upsert_rating_period(self, row, *, conflict_fields, update_fields):
        self.period_writes.append((row, conflict_fields, update_fields))

    def upsert_rating_result(self, row, *, conflict_fields, update_fields):
        self.result_writes.append((row, conflict_fields, update_fields))


@pytest.mark.rule("RATING-008")
@pytest.mark.rule("RATING-009")
def test_finalize_proposes_stable_ids_unused_quota_and_narrow_conflict_updates(rating_api):
    repository = RecordingRepository(rating_api)
    for end in [END, date(2026, 2, 27)]:
        rating_api.finalize_rating(repository, TENANT, START, end, session_timezone=UTC)
    period_id = UUID(hashlib.md5(f"{TENANT}{START}".encode(), usedforsecurity=False).hexdigest())
    result_id = UUID(hashlib.md5(str(period_id).encode(), usedforsecurity=False).hexdigest())
    for (period, period_conflict, period_update), (result, conflict, update) in zip(
        repository.period_writes,
        repository.result_writes,
        strict=True,
    ):
        assert (period.id, period.tenant_id, period.period_start) == (period_id, TENANT, START)
        assert set(period_conflict) == {"tenant_id", "period_start"}
        assert set(period_update) == {"period_end"}
        assert (result.id, result.period_id, result.subscription_id) == (
            result_id,
            period_id,
            UUID(int=20),
        )
        assert (
            result.used_units,
            result.quota_units,
            result.rollover_units,
            result.billable_units,
            result.overage_amount,
        ) == (25, 100, 75, 0, Decimal("0.00"))
        assert result.created_at == datetime.combine(period.period_end, datetime.min.time(), UTC)
        assert set(conflict) == {"id"}
        assert set(update) == {"used_units", "rollover_units", "billable_units", "overage_amount"}
    assert [row.period_end for row, _, _ in repository.period_writes] == [END, date(2026, 2, 27)]


@pytest.mark.rule("RATING-008")
def test_finalize_propagates_repository_failure(rating_api):
    class UnavailableRepository(RecordingRepository):
        def upsert_rating_period(self, row, *, conflict_fields, update_fields):
            raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        rating_api.finalize_rating(
            UnavailableRepository(rating_api),
            TENANT,
            START,
            END,
            session_timezone=UTC,
        )
