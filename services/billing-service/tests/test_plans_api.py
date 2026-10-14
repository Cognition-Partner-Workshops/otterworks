from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

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


class FakeRepository:
    def __init__(self, _database: object) -> None:
        return None

    def run_in_transaction(self, operation):
        return operation()


def test_repeated_plan_change_returns_conflict(monkeypatch) -> None:
    calls = 0

    def fake_change_plan(*_args: object) -> tuple[list[SubscriptionRow], SubscriptionRow]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise DuplicateKeyError("duplicate subscription")
        return [CREATED], CREATED

    monkeypatch.setattr(main, "database", lambda: None)
    monkeypatch.setattr(main, "MongoPlansRepository", FakeRepository)
    monkeypatch.setattr(main, "change_plan", fake_change_plan)
    with TestClient(main.app) as client:
        payload = {"plan_id": str(PLAN), "effective_on": "2026-03-01"}
        first = client.post(f"/api/tenants/{TENANT}/plan-change", json=payload)
        second = client.post(f"/api/tenants/{TENANT}/plan-change", json=payload)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"] == "this plan change has already been requested"
