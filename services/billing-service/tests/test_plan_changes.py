from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from test_domain import FakeRepository
from test_plans_api import FakeConnection

import app.main as main
from app.domain import PlanRow, SubscriptionRow
from app.plan_changes import (
    PlanChangeError,
    apply_plan_change,
    billing_cycle,
    quote_plan_change,
    upgrade_lines,
)


@pytest.mark.parametrize(
    ("anchor", "on", "start", "next_start"),
    [
        # Month lengths by hand: 28, 31, 30, 31 days; leap January cycle is 29.
        ("2026-01-31", "2026-02-01", "2026-01-31", "2026-02-28"),
        ("2026-01-31", "2026-03-01", "2026-02-28", "2026-03-31"),
        ("2026-01-31", "2026-04-01", "2026-03-31", "2026-04-30"),
        ("2026-01-31", "2026-05-01", "2026-04-30", "2026-05-31"),
        ("2028-01-31", "2028-02-01", "2028-01-31", "2028-02-29"),
        ("2028-01-31", "2028-03-01", "2028-02-29", "2028-03-31"),
        ("2028-02-29", "2028-03-29", "2028-03-29", "2028-04-29"),
        ("2028-02-29", "2029-02-28", "2029-02-28", "2029-03-29"),
        ("2026-01-29", "2026-02-28", "2026-02-28", "2026-03-29"),
        ("2026-01-30", "2026-02-28", "2026-02-28", "2026-03-30"),
        ("2028-01-29", "2028-02-29", "2028-02-29", "2028-03-29"),
        ("2028-01-30", "2028-02-29", "2028-02-29", "2028-03-30"),
        ("2026-01-31", "2026-12-31", "2026-12-31", "2027-01-31"),
        ("2026-01-31", "2027-01-30", "2026-12-31", "2027-01-31"),
    ],
)
def test_cycle(anchor, on, start, next_start):
    assert billing_cycle(date.fromisoformat(anchor), date.fromisoformat(on)) == (
        date.fromisoformat(start),
        date.fromisoformat(next_start),
    )


@pytest.mark.parametrize(
    ("old", "new", "remaining", "days", "due", "credit", "charge"),
    [
        # 100*17/31=54.8387; 49*17/31=26.8709; 54.84+26.87=81.71.
        ("49", "149", 17, 31, "54.84", "-26.87", "81.71"),
        # Full difference on day one; 100/31=3.2258 on the final day.
        ("49", "149", 31, 31, "100.00", "-49.00", "149.00"),
        ("49", "149", 1, 31, "3.23", "-1.58", "4.81"),
        # One cent / two days = half a cent, rounds UP once.
        ("0.00", "0.01", 1, 2, "0.01", "0.00", "0.01"),
    ],
)
def test_exact_money(old, new, remaining, days, due, credit, charge):
    assert upgrade_lines(Decimal(old), Decimal(new), remaining, days) == (
        Decimal(due),
        Decimal(credit),
        Decimal(charge),
    )


@pytest.mark.parametrize("start", ["2026-01-31", "2026-02-28", "2028-01-31", "2028-02-29"])
def test_each_day(start):
    anchor = date(2026, 1, 31)
    start, end = billing_cycle(anchor, date.fromisoformat(start))
    previous = Decimal("100")
    for offset in range((end - start).days):
        on = start + timedelta(days=offset)
        due, credit, charge = upgrade_lines(
            Decimal("49"), Decimal("149"), (end - on).days, (end - start).days
        )
        assert credit + charge == due
        assert Decimal("0") <= due <= previous <= Decimal("100")
        previous = due


TENANT = UUID(int=1)
STARTER, GROWTH, SCALE, INACTIVE = [UUID(int=n) for n in range(10, 14)]


class Repository(FakeRepository):
    def __init__(self, plan=STARTER, starts_on=date(2026, 1, 1), status="active"):
        super().__init__(
            [SubscriptionRow(UUID(int=20), TENANT, plan, starts_on, None, status, None)]
        )
        self.invoices = []

    def list_plans(self):
        return [
            PlanRow(pid, code, code.lower(), Decimal(fee), 1, Decimal("0"), active)
            for pid, code, fee, active in [
                (STARTER, "STARTER", "49", True),
                (GROWTH, "GROWTH", "149", True),
                (SCALE, "SCALE", "499", True),
                (INACTIVE, "OLD", "1", False),
            ]
        ]

    def lock_tenant(self, _tenant):
        pass

    def invoice_exists(self, invoice_id):
        return any(i["id"] == str(invoice_id) for i in self.invoices)

    def delete_pending_subscriptions(self, _tenant, on):
        self.subscriptions = [s for s in self.subscriptions if s.starts_on <= on]

    def reopen_subscription(self, subscription_id):
        self.subscriptions = [
            replace(s, ends_on=None) if s.subscription_id == subscription_id else s
            for s in self.subscriptions
        ]

    def set_subscription_plan(self, subscription_id, plan_id):
        self.subscriptions = [
            replace(s, plan_id=plan_id) if s.subscription_id == subscription_id else s
            for s in self.subscriptions
        ]

    def insert_invoice(self, invoice):
        self.invoices.append(invoice)

    def list_invoices(self, _tenant):
        return list(reversed(self.invoices))


def test_upgrade_quote_has_customer_lines_and_no_writes():
    repo = Repository()
    result = quote_plan_change(repo, TENANT, GROWTH, date(2026, 3, 15))
    assert result["amount_due"] == "54.84"
    assert result["cycle_start"] == "2026-03-01"
    assert result["cycle_end"] == "2026-03-31"
    assert result["days_remaining"] == 17
    assert result["lines"][0]["description"] == (
        "Credit for unused time on Starter, Mar 15, 2026 – Mar 31, 2026 (17 of 31 days)"
    )
    assert repo.invoices == []
    assert len(repo.subscriptions) == 1
    assert not repo.updates


def test_downgrade():
    repo = Repository(SCALE, date(2026, 1, 31))
    result = apply_plan_change(repo, TENANT, GROWTH, date(2026, 2, 15))
    # January 31 + 28 days = February 28 renewal, no immediate charge.
    assert result["effective_on"] == "2026-02-28"
    assert result["amount_due"] == "0.00"
    assert result["lines"] == []
    assert result["invoice"] is None
    assert repo.subscriptions[0].ends_on == date(2026, 2, 27)
    assert repo.subscriptions[1].starts_on == date(2026, 2, 28)


def test_same_day_double_upgrade_and_idempotency():
    repo = Repository()
    first = apply_plan_change(repo, TENANT, GROWTH, date(2026, 3, 15))
    second = apply_plan_change(repo, TENANT, SCALE, date(2026, 3, 15))
    # Second difference 350 * 17/31 = 191.93548 -> 191.94, not 450*17/31.
    assert first["amount_due"] == "54.84"
    assert second["amount_due"] == "191.94"
    assert len(repo.subscriptions) == 2
    assert repo.subscriptions[-1].plan_id == SCALE
    assert len(repo.invoices) == 2
    with pytest.raises(PlanChangeError) as error:
        apply_plan_change(repo, TENANT, SCALE, date(2026, 3, 15))
    assert error.value.status == 409


@pytest.mark.parametrize("new", [STARTER, SCALE])
def test_replace_pending_downgrade(new):
    repo = Repository(GROWTH)
    apply_plan_change(repo, TENANT, STARTER, date(2026, 3, 10))
    result = apply_plan_change(repo, TENANT, new, date(2026, 3, 15))
    assert len(repo.subscriptions) == 2
    assert repo.subscriptions[-1].plan_id == new
    assert repo.subscriptions[-1].starts_on == date.fromisoformat(result["effective_on"])
    assert repo.subscriptions[0].ends_on == (
        date.fromisoformat(result["effective_on"]) - timedelta(days=1)
    )


@pytest.mark.parametrize(
    ("plan", "on", "status", "expected", "message"),
    [
        (STARTER, "2026-03-15", "active", 409, "You're already on this plan"),
        (UUID(int=999), "2026-03-15", "active", 404, "Plan not found"),
        (INACTIVE, "2026-03-15", "active", 400, "no longer available"),
        (GROWTH, "2025-12-31", "active", 404, "No subscription"),
        (GROWTH, "2026-03-15", "suspended", 409, "suspended"),
        (GROWTH, "2026-03-15", "cancelled", 409, "cancelled"),
    ],
)
def test_rejections(plan, on, status, expected, message):
    repo = Repository(status=status)
    with pytest.raises(PlanChangeError) as error:
        apply_plan_change(repo, TENANT, plan, date.fromisoformat(on))
    assert error.value.status == expected
    assert message in error.value.message
    assert repo.invoices == []
    assert not repo.updates


def test_new_routes(monkeypatch):
    repo = Repository()
    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "PostgresPlansRepository", lambda _: repo)
    base = f"/api/tenants/{TENANT}"
    with TestClient(main.app) as client:
        assert client.get(f"{base}/invoices").json() == []
        quote = client.get(
            f"{base}/plan-change-quote", params={"plan_id": str(GROWTH), "on": "2026-03-15"}
        )
        assert quote.status_code == 200
        assert repo.invoices == []
        payload = {"plan_id": str(GROWTH), "requested_on": "2026-03-15"}
        applied = client.post(f"{base}/plan-changes", json=payload)
        assert applied.status_code == 200
        assert {k: applied.json()[k] for k in quote.json()} == quote.json()
        assert client.get(f"{base}/invoices").json() == [applied.json()["invoice"]]
        assert client.post(f"{base}/plan-changes", json=payload).status_code == 409
        assert (
            client.get(
                f"{base}/plan-change-quote", params={"plan_id": str(INACTIVE), "on": "2026-03-15"}
            ).status_code
            == 400
        )
        downgrade = client.post(
            f"{base}/plan-changes", json={"plan_id": str(STARTER), "requested_on": "2026-03-16"}
        )
        assert downgrade.status_code == 200
        assert downgrade.json()["invoice"] is None
        assert client.post(f"{base}/plan-changes", json={"plan_id": "bad"}).status_code == 422


def test_requested_on_defaults_to_server_today(monkeypatch):
    repo = Repository()
    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "PostgresPlansRepository", lambda _: repo)
    with TestClient(main.app) as client:
        result = client.post(f"/api/tenants/{TENANT}/plan-changes", json={"plan_id": str(GROWTH)})
    assert result.status_code == 200
    assert result.json()["requested_on"] == date.today().isoformat()
