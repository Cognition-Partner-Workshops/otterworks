from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.domain import PlanRow, SubscriptionRow
from app.rating_domain import UsageEventRow

TENANT = UUID(int=1)
PLAN = UUID(int=10)
PERIOD = {"period_start": "2026-02-01", "period_end": "2026-02-28"}


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class FakeRepository:
    def __init__(self, _connection):
        self.result = None

    def session_timezone(self):
        return UTC

    def list_plans(self):
        return [PlanRow(PLAN, "TEST", "starter", Decimal("49"), 100, Decimal("0.055"), True)]

    def list_subscriptions(self, tenant_id):
        return [SubscriptionRow(UUID(int=20), TENANT, PLAN, date(2026, 1, 1), None, "active", None)]

    def list_usage_events(self, tenant_id):
        return [UsageEventRow(TENANT, datetime(2026, 2, 10, tzinfo=UTC), 201, "api")]

    def list_prior_rating_results(self, tenant_id):
        return []

    def upsert_rating_period(self, row, **_kwargs):
        self.period = row

    def upsert_rating_result(self, row, **_kwargs):
        self.result = row

    def rating_results(self, tenant_id, period_start):
        assert (tenant_id, period_start) == (TENANT, date(2026, 2, 1))
        return [replace(self.result, quota_units=777)]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "PostgresRatingRepository", FakeRepository)
    with TestClient(main.app) as client:
        yield client


def test_rating_serializes_decimal_and_all_rating_fields(client):
    response = client.get(f"/api/tenants/{TENANT}/rating", params=PERIOD)
    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": str(TENANT),
        **PERIOD,
        "used_units": 201,
        "quota_units": 100,
        "rollover_units": 0,
        "billable_units": 101,
        "first_tier_units": 101,
        "second_tier_units": 0,
        "overage_amount": "5.56",
    }


def test_summary_returns_counts_and_empty_list(client, monkeypatch):
    response = client.get(f"/api/tenants/{TENANT}/usage-summary", params=PERIOD)
    assert response.status_code == 200
    assert response.json() == [{"kind": "api", "event_count": 1, "units": 201}]
    monkeypatch.setattr(FakeRepository, "list_usage_events", lambda *_: [])
    assert client.get(f"/api/tenants/{TENANT}/usage-summary", params=PERIOD).json() == []
    rating = client.get(f"/api/tenants/{TENANT}/rating", params=PERIOD)
    assert rating.status_code == 200
    assert rating.json()["overage_amount"] == "0.00"


def test_finalize_returns_persisted_values_not_the_proposed_row(client):
    response = client.post(f"/api/tenants/{TENANT}/rating/finalize", json=PERIOD)
    assert response.status_code == 200
    row = {
        "used_units": 201,
        "quota_units": 777,
        "rollover_units": 0,
        "billable_units": 101,
        "overage_amount": "5.56",
    }
    assert response.json() == {**row, "rating_result": [row]}


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "rating"),
        ("GET", "usage-summary"),
        ("POST", "rating/finalize"),
    ],
)
def test_invalid_period_is_rejected(client, method, path):
    period = {**PERIOD, "period_end": "2026-01-31"}
    kwargs = {"json" if method == "POST" else "params": period}
    assert client.request(method, f"/api/tenants/{TENANT}/{path}", **kwargs).status_code == 422


@pytest.mark.parametrize("path", ["rating", "rating/finalize"])
def test_missing_subscription_is_not_found(client, monkeypatch, path):
    monkeypatch.setattr(FakeRepository, "list_subscriptions", lambda *_: [])
    method = "POST" if path.endswith("finalize") else "GET"
    kwargs = {"json" if method == "POST" else "params": PERIOD}
    response = client.request(method, f"/api/tenants/{TENANT}/{path}", **kwargs)
    assert response.status_code == 404


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "rating"),
        ("GET", "usage-summary"),
        ("POST", "rating/finalize"),
    ],
)
def test_database_failure_is_unavailable(client, monkeypatch, method, path):
    def unavailable():
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(main, "connect", unavailable)
    kwargs = {"json" if method == "POST" else "params": PERIOD}
    response = client.request(method, f"/api/tenants/{TENANT}/{path}", **kwargs)
    assert response.status_code == 503
    assert response.json()["detail"] == "database unavailable"
