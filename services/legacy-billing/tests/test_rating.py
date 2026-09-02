"""Unit tests for the PKG_RATING port (ow_billing.rating).

Run from services/legacy-billing:
    uv run --with pytest --with mongomock --with pymongo pytest tests/test_rating.py
"""

# ruff: noqa: DTZ001
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import mongomock
import pytest
from bson import Decimal128, Int64

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from ow_billing import NS_VALUE, rating

TENANT = "00000000-0000-0000-0000-000000000001"
FEB1, FEB28 = date(2026, 2, 1), date(2026, 2, 28)


def _store(prefix: str = "replay_u7_") -> rating.RatingStore:
    return rating.RatingStore(mongomock.MongoClient()["ow_tp_mongodb_205236"], prefix)


def _seed(store, *, included=100, rate="0.05", status=10, suspended_on=None, plan=True):
    store.subscriptions.insert_one(
        {
            "_id": "sub-1",
            "id": "sub-1",
            "tenant_id": TENANT,
            "plan_id": "plan-1",
            "starts_on": datetime(2026, 1, 1),
            "ends_on": None,
            "status_cd": status,
            "suspended_on": suspended_on,
            "ns": NS_VALUE,
        }
    )
    if plan:
        store.plans.insert_one(
            {
                "_id": "plan-1",
                "id": "plan-1",
                "included_units": Int64(included),
                "overage_rate": Decimal128(rate),
                "ns": NS_VALUE,
            }
        )


def _event(store, ident, when, units, kind=1):
    store.usage_events.insert_one(
        {
            "_id": ident,
            "id": ident,
            "tenant_id": TENANT,
            "occurred_at": when,
            "units": None if units is None else Int64(units),
            "kind_cd": kind,
            "ns": NS_VALUE,
        }
    )


def test_null_propagation_matches_oracle():
    assert rating.least(Decimal(1), None) is None
    assert rating.greatest(None, Decimal(0)) is None
    assert rating.nvl(None, Decimal(7)) == 7
    assert rating.oracle_round(Decimal("2.5")) == 3
    assert rating.oracle_round(Decimal("4.365"), 2) == Decimal("4.37")
    assert rating.oracle_round(None, 2) is None


def test_add_months_clamps_to_month_end():
    assert rating.add_months(datetime(2026, 5, 31), -3) == datetime(2026, 2, 28)
    assert rating.add_months(datetime(2026, 2, 1), -3) == datetime(2025, 11, 1)
    assert rating.add_months(datetime(2026, 2, 28), -3) == datetime(2025, 11, 30)


def test_md5_uuid_layout():
    value = rating.md5_uuid(f"{TENANT}2026-02-01")
    assert len(value) == 36 and value.count("-") == 4 and value == value.lower()


def test_string_window_includes_whole_end_day_and_nvl_units():
    store = _store()
    _seed(store)
    _event(store, "e1", datetime(2026, 1, 31, 23, 59, 59), 1000)  # before window
    _event(store, "e2", datetime(2026, 2, 28, 23, 59, 59), 150)  # end day counts
    _event(store, "e3", datetime(2026, 2, 10), None)  # NVL(units, 0)
    _event(store, "e4", datetime(2026, 3, 1, 0, 0, 0), 500)  # after window
    r = rating.compute_rating(store, TENANT, FEB1, FEB28)
    assert r.used_units == 150
    assert r.quota_units == 100
    assert r.rollover_units == 0
    assert r.billable_units == 50
    assert r.first_tier_units == 50 and r.second_tier_units == 0
    assert r.overage_amount == Decimal("2.50")


def test_tiers_and_rounding():
    store = _store()
    _seed(store, included=100, rate="0.0333")
    _event(store, "e1", datetime(2026, 2, 5), 301)
    r = rating.compute_rating(store, TENANT, FEB1, FEB28)
    assert r.billable_units == 201
    assert r.first_tier_units == 101 and r.second_tier_units == 100
    assert r.overage_amount == Decimal("8.36")  # ROUND(101*.0333 + 100*.0333*1.5, 2)


def test_rollover_capped_at_twice_included_and_window_is_three_months():
    store = _store()
    _seed(store, included=100)
    for month, banked in ((11, 150), (12, 150), (1, 150), (10, 999)):
        year = 2026 if month == 1 else 2025
        store.rating_periods.insert_one(
            {
                "_id": f"p{month}",
                "tenant_id": TENANT,
                "period_start": datetime(year, month, 1),
                "period_end": datetime(year, month, 28),
                "results": [{"id": f"r{month}", "rollover_units": Int64(banked)}],
                "ns": NS_VALUE,
            }
        )
    _event(store, "e1", datetime(2026, 2, 5), 360)
    r = rating.compute_rating(store, TENANT, FEB1, FEB28)
    assert r.rollover_units == 200  # LEAST(450, 2*100); October is outside ADD_MONTHS(-3)
    assert r.billable_units == 60


def test_no_plan_propagates_null_like_oracle():
    store = _store()
    _seed(store, plan=False)
    _event(store, "e1", datetime(2026, 2, 5), 360)
    r = rating.compute_rating(store, TENANT, FEB1, FEB28)
    assert r.quota_units is None
    assert r.rollover_units == 0
    assert r.billable_units == 0
    assert r.overage_amount is None


def test_suspension_proration_for_status_20():
    store = _store()
    _seed(store, included=100, rate="0.10", status=20, suspended_on=datetime(2026, 2, 15))
    _event(store, "e1", datetime(2026, 2, 5), 300)
    r = rating.compute_rating(store, TENANT, FEB1, FEB28)
    # factor = (28-15+1)/28 = 0.5; billable 200 -> 100;
    # overage ROUND((101*.10 + 99*.10*1.5) * 0.5, 2) = ROUND(12.475, 2) = 12.48
    assert r.billable_units == 100
    assert r.overage_amount == Decimal("12.48")
    store2 = _store()
    _seed(store2, included=100, rate="0.10", status=10, suspended_on=datetime(2026, 2, 15))
    _event(store2, "e1", datetime(2026, 2, 5), 300)
    assert rating.compute_rating(store2, TENANT, FEB1, FEB28).billable_units == 200


def test_usage_summary_decodes_kinds_and_sorts():
    store = _store()
    _event(store, "e1", datetime(2026, 2, 5), 20, kind=1)
    _event(store, "e2", datetime(2026, 2, 6), 30, kind=2)
    _event(store, "e3", datetime(2026, 2, 7), 5, kind=9)
    _event(store, "e4", datetime(2026, 3, 7), 5, kind=3)
    rows = rating.fn_usage_summary(store, TENANT, FEB1, FEB28)
    assert [(r["kind"], r["event_count"], r["units"]) for r in rows] == [
        ("UNKNOWN", 1, 5),
        ("api", 1, 20),
        ("storage", 1, 30),
    ]


def test_finalize_upserts_single_embedded_result_and_is_idempotent():
    store = _store()
    _seed(store, included=100, rate="0.05")
    _event(store, "e1", datetime(2026, 2, 5), 60)
    first = rating.sp_finalize_rating(store, TENANT, FEB1, FEB28)
    period_id = rating.md5_uuid(f"{TENANT}2026-02-01")
    assert first["_id"] == first["id"] == period_id
    assert first["ns"] == NS_VALUE
    assert len(first["results"]) == 1
    result = first["results"][0]
    assert result["id"] == rating.md5_uuid(period_id)
    assert result["subscription_id"] == "sub-1"
    assert result["used_units"] == 60 and isinstance(result["used_units"], Int64)
    assert result["rollover_units"] == 40  # GREATEST(quota - used, 0)
    assert result["overage_amount"] == Decimal128("0.00")
    assert result["created_at"] == datetime(2026, 2, 28)

    _event(store, "e2", datetime(2026, 2, 6), 200)
    second = rating.sp_finalize_rating(store, TENANT, FEB1, date(2026, 2, 27))
    assert len(second["results"]) == 1
    assert second["period_end"] == datetime(2026, 2, 27)
    assert second["results"][0]["used_units"] == 260
    assert second["results"][0]["rollover_units"] == 0
    assert second["results"][0]["billable_units"] == 160
    assert second["results"][0]["overage_amount"] == Decimal128("9.48")  # ROUND(101*.05 + 59*.05*1.5, 2)
    assert store.rating_periods.count_documents({}) == 1
    assert store.billing_audit_log.count_documents({"module": "RATING"}) == 4
    assert rating.rating_result_rows(store, TENANT, FEB1)[0]["billable_units"] == 160


def test_store_prefix_isolates_replay_clone():
    store = _store("replay_u7_")
    assert store.rating_periods.name == "replay_u7_rating_periods"
    assert rating.RatingStore(store.db).usage_events.name == "usage_events"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
