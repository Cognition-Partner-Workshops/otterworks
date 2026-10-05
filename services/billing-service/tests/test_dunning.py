from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.domain import (
    DunningAttemptRow,
    DunningInvoiceRow,
    NotificationRow,
    SubscriptionRow,
    dunning_attempt_id,
    dunning_schedule_date,
    overdue_accounts,
    schedule_dunning,
    suspend_overdue,
    suspension_notification_id,
)

TENANT_1 = UUID("00000000-0000-0000-0000-000000000001")
TENANT_2 = UUID("00000000-0000-0000-0000-000000000002")
TENANT_3 = UUID("00000000-0000-0000-0000-000000000003")
TENANT_5 = UUID("00000000-0000-0000-0000-000000000005")
PLAN = UUID("10000000-0000-0000-0000-000000000001")
INVOICE_1 = UUID("60000000-0000-0000-0000-000000000001")
INVOICE_2 = UUID("60000000-0000-0000-0000-000000000002")


def invoice(
    invoice_id: UUID,
    tenant_id: UUID,
    issued_at: str,
    *,
    status: str = "overdue",
    tenant_status: str = "active",
) -> DunningInvoiceRow:
    return DunningInvoiceRow(
        invoice_id=invoice_id,
        tenant_id=tenant_id,
        issued_at=datetime.fromisoformat(issued_at),
        total=Decimal("161.29"),
        status=status,
        tenant_status=tenant_status,
    )


def subscription(
    subscription_id: str,
    tenant_id: UUID,
    status: str = "active",
) -> SubscriptionRow:
    return SubscriptionRow(
        subscription_id=UUID(subscription_id),
        tenant_id=tenant_id,
        plan_id=PLAN,
        starts_on=date(2026, 3, 1),
        ends_on=None,
        status=status,
        suspended_on=None,
    )


class FakeDunningRepository:
    def __init__(
        self,
        invoices: list[DunningInvoiceRow],
        *,
        attempts: list[DunningAttemptRow] | None = None,
        tenant_statuses: dict[UUID, str] | None = None,
        subscriptions: list[SubscriptionRow] | None = None,
        notifications: list[NotificationRow] | None = None,
    ) -> None:
        self.invoices = invoices
        self.attempts = list(attempts or [])
        self.tenant_statuses = tenant_statuses or {
            row.tenant_id: row.tenant_status for row in invoices
        }
        self.subscriptions = list(subscriptions or [])
        self.notifications = list(notifications or [])

    def list_dunning_invoices(self) -> list[DunningInvoiceRow]:
        return list(self.invoices)

    def max_attempt_no(self, invoice_id: UUID) -> int:
        return max(
            (
                attempt.attempt_no
                for attempt in self.attempts
                if attempt.invoice_id == invoice_id
            ),
            default=0,
        )

    def insert_dunning_attempt(self, attempt: DunningAttemptRow) -> bool:
        if any(
            row.invoice_id == attempt.invoice_id and row.attempt_no == attempt.attempt_no
            for row in self.attempts
        ):
            return False
        self.attempts.append(attempt)
        return True

    def list_dunning_attempts(self) -> list[DunningAttemptRow]:
        return sorted(self.attempts, key=lambda row: (row.invoice_id, row.attempt_no))

    def tenant_status(self, tenant_id: UUID) -> str | None:
        return self.tenant_statuses.get(tenant_id)

    def suspend_tenant(self, tenant_id: UUID) -> None:
        self.tenant_statuses[tenant_id] = "suspended"

    def suspend_active_subscriptions(
        self,
        tenant_id: UUID,
        on: date,
    ) -> list[SubscriptionRow]:
        changed = []
        subscriptions = []
        for row in self.subscriptions:
            if row.tenant_id == tenant_id and row.status == "active":
                row = replace(row, status="suspended", suspended_on=on)
                changed.append(row)
            subscriptions.append(row)
        self.subscriptions = subscriptions
        return changed

    def suspension_notification_exists(self, tenant_id: UUID, sent_at: datetime) -> bool:
        return any(
            row.tenant_id == tenant_id and row.kind == "suspension" and row.sent_at == sent_at
            for row in self.notifications
        )

    def insert_notification(self, notification: NotificationRow) -> None:
        self.notifications.append(notification)

    def list_suspension_notifications(self) -> list[NotificationRow]:
        return sorted(
            (row for row in self.notifications if row.kind == "suspension"),
            key=lambda row: (row.tenant_id, row.sent_at),
        )


@pytest.mark.rule("DUNNING-001")
def test_overdue_accounts_filter_order_and_include_suspended_tenants() -> None:
    rows = [
        invoice(
            INVOICE_2,
            TENANT_5,
            "2026-02-13T00:00:00+00:00",
        ),
        invoice(
            INVOICE_1,
            TENANT_2,
            "2026-02-01T00:00:00+00:00",
            tenant_status="suspended",
        ),
        invoice(
            UUID("60000000-0000-0000-0000-000000000003"),
            TENANT_1,
            "2026-02-28T00:00:00+00:00",
        ),
        invoice(
            UUID("60000000-0000-0000-0000-000000000004"),
            TENANT_3,
            "2026-02-01T00:00:00+00:00",
            status="issued",
        ),
    ]

    actual = overdue_accounts(rows, date(2026, 2, 28))

    assert [row.tenant_id for row in actual] == [TENANT_2, TENANT_5]
    assert [row.days_overdue for row in actual] == [27, 15]
    assert actual[0].tenant_status == "suspended"


@pytest.mark.rule("DUNNING-001")
def test_overdue_accounts_truncate_issued_at_in_utc_and_break_ties_by_invoice_id() -> None:
    early = invoice(
        UUID("60000000-0000-0000-0000-000000000001"),
        TENANT_1,
        "2026-02-13T23:30:00-05:00",
    )
    late = invoice(
        UUID("60000000-0000-0000-0000-000000000002"),
        TENANT_2,
        "2026-02-14T04:30:00+00:00",
    )

    actual = overdue_accounts([late, early], date(2026, 2, 15))

    assert [row.invoice_id for row in actual] == [early.invoice_id, late.invoice_id]
    assert [row.days_overdue for row in actual] == [1, 1]


@pytest.mark.rule("DUNNING-002")
def test_schedule_counts_all_attempt_statuses_and_appends_each_call() -> None:
    scheduled_invoice = invoice(
        INVOICE_2,
        TENANT_5,
        "2026-02-13T00:00:00+00:00",
        tenant_status="active",
    )
    issued_after_as_of = invoice(
        INVOICE_1,
        TENANT_2,
        "2026-03-01T00:00:00+00:00",
        tenant_status="suspended",
    )
    not_overdue = invoice(
        UUID("60000000-0000-0000-0000-000000000003"),
        TENANT_1,
        "2026-02-01T00:00:00+00:00",
        status="issued",
    )
    sent_attempt = DunningAttemptRow(
        attempt_id=UUID("80000000-0000-0000-0000-000000000001"),
        tenant_id=TENANT_5,
        invoice_id=INVOICE_2,
        attempt_no=1,
        scheduled_for=date(2026, 2, 16),
        status="sent",
    )
    repository = FakeDunningRepository(
        [scheduled_invoice, issued_after_as_of, not_overdue],
        attempts=[sent_attempt],
        tenant_statuses={TENANT_5: "active", TENANT_2: "suspended", TENANT_1: "active"},
    )

    first = schedule_dunning(repository, date(2026, 2, 14))
    second = schedule_dunning(repository, date(2026, 2, 14))

    assert [(row.invoice_id, row.attempt_no) for row in first] == [
        (INVOICE_2, 2),
        (INVOICE_1, 1),
    ]
    assert [(row.invoice_id, row.attempt_no) for row in second] == [
        (INVOICE_2, 3),
        (INVOICE_1, 2),
    ]
    assert first[0].attempt_id == dunning_attempt_id(INVOICE_2, 2)
    assert first[0].attempt_id == UUID(
        hashlib.md5(f"{INVOICE_2}2".encode()).hexdigest()
    )
    assert first[0].scheduled_for == date(2026, 2, 16)
    assert first[0].tenant_id == TENANT_5


@pytest.mark.rule("DUNNING-003")
def test_dunning_schedule_moves_weekends_to_monday_only() -> None:
    assert dunning_schedule_date(date(2026, 2, 14)) == date(2026, 2, 16)
    assert dunning_schedule_date(date(2026, 2, 15)) == date(2026, 2, 16)
    assert dunning_schedule_date(date(2026, 2, 17)) == date(2026, 2, 17)
    assert dunning_schedule_date(date(2026, 2, 13)) == date(2026, 2, 13)


@pytest.mark.rule("DUNNING-004")
def test_suspension_uses_inclusive_grace_and_only_updates_active_rows() -> None:
    exact_threshold = invoice(
        INVOICE_1,
        TENANT_1,
        "2026-02-14T00:00:00+00:00",
    )
    inside_grace = invoice(
        INVOICE_2,
        TENANT_2,
        "2026-02-15T00:00:00+00:00",
    )
    already_suspended = invoice(
        UUID("60000000-0000-0000-0000-000000000003"),
        TENANT_3,
        "2026-02-01T00:00:00+00:00",
        tenant_status="suspended",
    )
    active = subscription("20000000-0000-0000-0000-000000000001", TENANT_1)
    cancelled = subscription(
        "20000000-0000-0000-0000-000000000002",
        TENANT_1,
        "cancelled",
    )
    old_suspended = replace(
        subscription("20000000-0000-0000-0000-000000000003", TENANT_3, "suspended"),
        suspended_on=date(2026, 2, 15),
    )
    repository = FakeDunningRepository(
        [exact_threshold, inside_grace, already_suspended],
        subscriptions=[active, cancelled, old_suspended],
        tenant_statuses={
            TENANT_1: "active",
            TENANT_2: "active",
            TENANT_3: "suspended",
        },
    )

    changed = suspend_overdue(repository, date(2026, 2, 28))

    assert [row.subscription_id for row in changed] == [active.subscription_id]
    assert changed[0].status == "suspended"
    assert changed[0].suspended_on == date(2026, 2, 28)
    assert repository.tenant_status(TENANT_1) == "suspended"
    assert repository.tenant_status(TENANT_2) == "active"
    assert repository.subscriptions[1] == cancelled
    assert repository.subscriptions[2] == old_suspended
    assert [row.tenant_id for row in repository.notifications] == [TENANT_1]


@pytest.mark.rule("DUNNING-005")
def test_suspension_notification_has_stable_id_utc_midnight_and_is_idempotent() -> None:
    repository = FakeDunningRepository(
        [
            invoice(
                INVOICE_2,
                TENANT_5,
                "2026-02-14T00:00:00+00:00",
            )
        ],
        tenant_statuses={TENANT_5: "active"},
    )
    expected_id = UUID("8cd558f5-d843-8d3d-be19-fb94c21ab81f")

    assert suspension_notification_id(TENANT_5, date(2026, 2, 28)) == expected_id
    suspend_overdue(repository, date(2026, 2, 28))
    suspend_overdue(repository, date(2026, 2, 28))

    assert len(repository.notifications) == 1
    assert repository.notifications[0].notification_id == expected_id
    assert repository.notifications[0].sent_at == datetime(
        2026, 2, 28, tzinfo=UTC
    )


def test_generated_dunning_seed_is_current() -> None:
    from scripts.generate_seed import generate_dunning

    seed_path = Path(__file__).parents[1] / "db" / "seed_dunning.sql"
    assert seed_path.read_text() == generate_dunning()


class FakeConnection:
    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_dunning_api_returns_exact_schedule_and_suspension_row_shapes(monkeypatch) -> None:
    fake_repository = FakeDunningRepository(
        [
            invoice(
                INVOICE_2,
                TENANT_5,
                "2026-02-01T00:00:00+00:00",
            )
        ],
        tenant_statuses={TENANT_5: "active"},
        subscriptions=[subscription("20000000-0000-0000-0000-000000000005", TENANT_5)],
    )
    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(
        main,
        "PostgresDunningRepository",
        lambda _connection: fake_repository,
    )

    with TestClient(main.app) as client:
        scheduled = client.post("/api/dunning/schedule", json={"as_of": "2026-02-14"})
        suspended = client.post("/api/dunning/suspend", json={"as_of": "2026-02-28"})

    assert scheduled.status_code == 200
    schedule_payload = scheduled.json()
    attempt_keys = {"invoice_id", "attempt_no", "scheduled_for", "status"}
    assert set(schedule_payload["created"][0]) == attempt_keys
    assert set(schedule_payload["latest_attempt"]) == attempt_keys
    assert set(schedule_payload["schedule_rows"][0]) == attempt_keys

    assert suspended.status_code == 200
    suspend_payload = suspended.json()
    subscription_keys = {"tenant_id", "subscription_id", "status", "suspended_on"}
    notification_keys = {"id", "tenant_id", "kind", "sent_at"}
    assert set(suspend_payload["suspended_subscriptions"][0]) == subscription_keys
    assert set(suspend_payload["latest_suspension"]) == subscription_keys
    assert set(suspend_payload["suspension_notifications"][0]) == notification_keys
    assert suspend_payload["suspension_notifications"][0]["sent_at"] == (
        "2026-02-28T00:00:00Z"
    )
