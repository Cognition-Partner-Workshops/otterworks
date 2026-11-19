from __future__ import annotations

from dataclasses import replace
from datetime import date
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.domain import SubscriptionRow

TENANT = UUID("00000000-0000-0000-0000-000000000001")
PLAN = UUID("10000000-0000-0000-0000-000000000002")
CREATED = SubscriptionRow(
    UUID("20000000-0000-0000-0000-000000000003"),
    TENANT,
    PLAN,
    date(2026, 3, 1),
    None,
    "active",
    None,
)


class FakeConnection:
    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class FakeRepository:
    def __init__(self) -> None:
        self.subscriptions = [
            replace(
                CREATED,
                plan_id=UUID("10000000-0000-0000-0000-000000000001"),
                starts_on=date(2026, 1, 1),
            )
        ]

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        return [item for item in self.subscriptions if item.tenant_id == tenant_id]

    def update_subscription(self, subscription_id: UUID, ends_on: date, status: str) -> None:
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
        if any(item.subscription_id == subscription_id for item in self.subscriptions):
            raise psycopg.errors.UniqueViolation("duplicate subscription")
        self.subscriptions.append(
            SubscriptionRow(subscription_id, tenant_id, plan_id, starts_on, None, status, None)
        )


@pytest.fixture
def plan_client(monkeypatch):
    repository = FakeRepository()
    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "PostgresPlansRepository", lambda _connection: repository)
    with TestClient(main.app) as client:
        yield client, repository


def test_backdated_plan_change_is_rejected(plan_client) -> None:
    client, _repository = plan_client
    response = client.post(
        f"/api/tenants/{TENANT}/plan-change",
        json={"plan_id": str(PLAN), "effective_on": "2025-12-31"},
    )
    assert response.status_code == 400
    assert "before" in response.json()["detail"]
    assert "subscription start" in response.json()["detail"]


def test_rejected_plan_change_preserves_subscription_state(plan_client) -> None:
    client, repository = plan_client
    before = list(repository.subscriptions)
    client.post(
        f"/api/tenants/{TENANT}/plan-change",
        json={"plan_id": str(PLAN), "effective_on": "2025-12-31"},
    )
    assert len(repository.subscriptions) == len(before)
    assert repository.subscriptions == before


def test_future_plan_change_closes_prior_and_starts_selected_plan(plan_client) -> None:
    client, repository = plan_client
    response = client.post(
        f"/api/tenants/{TENANT}/plan-change",
        json={"plan_id": str(PLAN), "effective_on": "2026-03-01"},
    )
    assert response.status_code == 200
    prior, created = repository.subscriptions
    assert prior.ends_on == date(2026, 2, 28)
    assert created.plan_id == PLAN
    assert created.starts_on == date(2026, 3, 1)
    assert created.ends_on is None
    assert created.status == "active"


def test_repeated_plan_change_is_idempotent(plan_client) -> None:
    client, repository = plan_client
    payload = {"plan_id": str(PLAN), "effective_on": "2026-03-01"}
    first = client.post(f"/api/tenants/{TENANT}/plan-change", json=payload)
    before = list(repository.subscriptions)
    second = client.post(f"/api/tenants/{TENANT}/plan-change", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert len(repository.subscriptions) == len(before) == 2
    assert repository.subscriptions == before
