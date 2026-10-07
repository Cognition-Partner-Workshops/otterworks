from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.domain import (
    NoRatingSubscriptionError,
    Rating,
    RatingResultRow,
    UsageEventRow,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")
PERIOD = {"period_start": "2026-02-01", "period_end": "2026-02-28"}


class FakeConnection:
    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class FakeRepository:
    def __init__(self, _connection: object) -> None:
        pass

    def list_usage_events(self, tenant_id: UUID) -> list[UsageEventRow]:
        return [
            UsageEventRow(tenant_id, date(2026, 2, 6), 30, "storage"),
            UsageEventRow(tenant_id, date(2026, 2, 5), 20, "api"),
            UsageEventRow(tenant_id, date(2026, 3, 1), 99, "compute"),
        ]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "PostgresRatingRepository", FakeRepository)
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.mark.rule("RATING-001")
def test_rating_without_subscription_returns_null_quota_and_amount(client, monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "usage_rating",
        lambda _repository, tenant_id, start, end: Rating(
            tenant_id, start, end, 260, None, 0, 0, 0, 0, None
        ),
    )
    response = client.get(f"/api/tenants/{TENANT}/rating", params=PERIOD)
    assert response.status_code == 200
    body = response.json()
    assert body["quota_units"] is None
    assert body["overage_amount"] is None
    assert body["used_units"] == 260


@pytest.mark.rule("RATING-005")
def test_rating_returns_amount_with_two_decimals(client, monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "usage_rating",
        lambda _repository, tenant_id, start, end: Rating(
            tenant_id, start, end, 201, 100, 0, 101, 101, 0, Decimal("5.56")
        ),
    )
    response = client.get(f"/api/tenants/{TENANT}/rating", params=PERIOD)
    assert response.json()["overage_amount"] == "5.56"
    assert response.json()["first_tier_units"] == 101


@pytest.mark.rule("RATING-007")
def test_usage_summary_returns_rows_sorted_by_kind(client) -> None:
    response = client.get(f"/api/tenants/{TENANT}/usage-summary", params=PERIOD)
    assert response.status_code == 200
    assert response.json()["rows"] == [
        {"kind": "api", "event_count": 1, "units": 20},
        {"kind": "storage", "event_count": 1, "units": 30},
    ]


@pytest.mark.rule("RATING-008")
def test_finalize_returns_persisted_result(client, monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "finalize_rating",
        lambda *_args: [RatingResultRow(260, 100, 0, 0, Decimal("0.00"))],
    )
    response = client.post(f"/api/tenants/{TENANT}/rating/finalize", json=PERIOD)
    assert response.status_code == 200
    expected = {
        "used_units": 260,
        "quota_units": 100,
        "rollover_units": 0,
        "billable_units": 0,
        "overage_amount": "0.00",
    }
    assert response.json()["rating_result"] == [expected]
    assert {key: response.json()[key] for key in expected} == expected


def test_finalize_without_subscription_is_unprocessable(client, monkeypatch) -> None:
    def no_subscription(*_args: object) -> list[RatingResultRow]:
        raise NoRatingSubscriptionError(TENANT)

    monkeypatch.setattr(main, "finalize_rating", no_subscription)
    response = client.post(f"/api/tenants/{TENANT}/rating/finalize", json=PERIOD)
    assert response.status_code == 422
