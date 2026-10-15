from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.domain import DunningAttemptRow, InvoiceRow, SubscriptionRow, legacy_uuid
from app.dunning import (
    NotificationRow,
    next_business_day,
    overdue_accounts,
    schedule_dunning,
    suspend_overdue,
    suspension_notification,
)

TENANT_TWO = UUID("00000000-0000-0000-0000-000000000002")
TENANT_FIVE = UUID("00000000-0000-0000-0000-000000000005")
TENANT_SIX = UUID("00000000-0000-0000-0000-000000000006")
GROWTH = UUID("10000000-0000-0000-0000-000000000002")
INVOICE_ONE = UUID("60000000-0000-0000-0000-000000000001")
INVOICE_TWO = UUID("60000000-0000-0000-0000-000000000002")
INVOICE_THREE = UUID("60000000-0000-0000-0000-000000000003")
AS_OF = date(2026, 2, 28)


def invoice(
    invoice_id: UUID,
    tenant_id: UUID,
    issued: date,
    status: str = "overdue",
    attempts: tuple[DunningAttemptRow, ...] = (),
) -> InvoiceRow:
    return InvoiceRow(
        invoice_id=invoice_id,
        tenant_id=tenant_id,
        period_id=UUID("40000000-0000-0000-0000-000000000001"),
        issued_at=datetime(issued.year, issued.month, issued.day, tzinfo=UTC),
        subtotal=Decimal("149.00"),
        tax=Decimal("12.29"),
        total=Decimal("161.29"),
        status=status,
        lines=(),
        dunning_attempts=attempts,
    )


SENT_ATTEMPT = DunningAttemptRow(
    UUID("80000000-0000-0000-0000-000000000001"), TENANT_FIVE, 1, date(2026, 2, 16), "sent"
)


class FakeDunningRepository:
    """The seed: invoice one (tenant two, suspended) issued 02-01, invoice two (tenant five,
    active, one sent attempt) issued 02-13, invoice three (tenant six) issued 02-28."""

    def __init__(self) -> None:
        self.invoices = {
            INVOICE_TWO: invoice(
                INVOICE_TWO, TENANT_FIVE, date(2026, 2, 13), attempts=(SENT_ATTEMPT,)
            ),
            INVOICE_ONE: invoice(INVOICE_ONE, TENANT_TWO, date(2026, 2, 1)),
            INVOICE_THREE: invoice(INVOICE_THREE, TENANT_SIX, date(2026, 2, 28), status="issued"),
        }
        self.tenants = {TENANT_TWO: "suspended", TENANT_FIVE: "active", TENANT_SIX: "active"}
        self.subscriptions = {
            TENANT_FIVE: [
                SubscriptionRow(
                    UUID("20000000-0000-0000-0000-000000000005"),
                    TENANT_FIVE,
                    GROWTH,
                    date(2026, 1, 1),
                    None,
                    "active",
                    None,
                )
            ],
            TENANT_TWO: [],
        }
        self.notifications: list[NotificationRow] = []
        self.suspended: list[tuple[UUID, date]] = []

    def list_overdue_invoices(self) -> list[InvoiceRow]:
        return [row for row in self.invoices.values() if row.status == "overdue"]

    def tenant_status(self, tenant_id: UUID) -> str | None:
        return self.tenants.get(tenant_id)

    def append_dunning_attempt(self, invoice_id: UUID, attempt: DunningAttemptRow) -> bool:
        row = self.invoices[invoice_id]
        if any(item.attempt_no == attempt.attempt_no for item in row.dunning_attempts):
            return False
        self.invoices[invoice_id] = replace(row, dunning_attempts=(*row.dunning_attempts, attempt))
        return True

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        return list(self.subscriptions.get(tenant_id, []))

    def suspend_tenant(self, tenant_id: UUID, as_of: date) -> list[SubscriptionRow]:
        self.suspended.append((tenant_id, as_of))
        self.tenants[tenant_id] = "suspended"
        self.subscriptions[tenant_id] = [
            replace(item, status="suspended", suspended_on=as_of)
            if item.status == "active"
            else item
            for item in self.subscriptions.get(tenant_id, [])
        ]
        return self.list_subscriptions(tenant_id)

    def list_notifications(self, kind: str, tenant_id: UUID | None = None) -> list[NotificationRow]:
        return [
            row
            for row in self.notifications
            if row.kind == kind and (tenant_id is None or row.tenant_id == tenant_id)
        ]

    def insert_notification(self, notification: NotificationRow) -> bool:
        key = (notification.tenant_id, notification.kind, notification.sent_at)
        if any((row.tenant_id, row.kind, row.sent_at) == key for row in self.notifications):
            return False
        self.notifications.append(notification)
        return True


@pytest.mark.rule("DUNNING-001")
def test_overdue_accounts_lists_overdue_invoices_issued_before_as_of_in_issue_order() -> None:
    rows = overdue_accounts(FakeDunningRepository(), AS_OF)

    assert [(row.tenant_id, row.invoice_id) for row in rows] == [
        (TENANT_TWO, INVOICE_ONE),
        (TENANT_FIVE, INVOICE_TWO),
    ]
    assert [row.days_overdue for row in rows] == [27, 15]
    assert [row.tenant_status for row in rows] == ["suspended", "active"]
    assert rows[0].total == Decimal("161.29")


@pytest.mark.rule("DUNNING-001")
def test_overdue_accounts_excludes_invoices_issued_on_as_of_and_orphans() -> None:
    repository = FakeDunningRepository()
    repository.invoices[INVOICE_THREE] = replace(
        repository.invoices[INVOICE_THREE], status="overdue"
    )
    del repository.tenants[TENANT_TWO]

    rows = overdue_accounts(repository, AS_OF)

    assert [row.invoice_id for row in rows] == [INVOICE_TWO]
    assert overdue_accounts(repository, date(2026, 3, 1))[-1].days_overdue == 1


@pytest.mark.rule("DUNNING-002")
def test_schedule_dunning_appends_the_next_attempt_per_overdue_invoice_with_legacy_ids() -> None:
    repository = FakeDunningRepository()

    scheduled = schedule_dunning(repository, date(2026, 2, 17))

    assert [(item.invoice.invoice_id, item.attempt.attempt_no) for item in scheduled] == [
        (INVOICE_ONE, 1),
        (INVOICE_TWO, 2),
    ]
    assert all(item.appended for item in scheduled)
    assert scheduled[1].attempt == DunningAttemptRow(
        legacy_uuid(INVOICE_TWO, 2), TENANT_FIVE, 2, date(2026, 2, 17), "scheduled"
    )
    assert repository.invoices[INVOICE_TWO].dunning_attempts == (SENT_ATTEMPT, scheduled[1].attempt)
    assert repository.invoices[INVOICE_THREE].dunning_attempts == ()


@pytest.mark.rule("DUNNING-002")
def test_schedule_dunning_moves_weekend_dates_to_monday() -> None:
    assert next_business_day(date(2026, 2, 14)) == date(2026, 2, 16)  # Saturday
    assert next_business_day(date(2026, 2, 15)) == date(2026, 2, 16)  # Sunday
    assert next_business_day(date(2026, 2, 16)) == date(2026, 2, 16)  # Monday
    assert next_business_day(date(2026, 2, 13)) == date(2026, 2, 13)  # Friday

    scheduled = schedule_dunning(FakeDunningRepository(), date(2026, 2, 14))

    assert {item.attempt.scheduled_for for item in scheduled} == {date(2026, 2, 16)}


class RacedDunningRepository(FakeDunningRepository):
    """Another run appended invoice one's next attempt between the read and the append."""

    def append_dunning_attempt(self, invoice_id: UUID, attempt: DunningAttemptRow) -> bool:
        if invoice_id == INVOICE_ONE:
            return False
        return super().append_dunning_attempt(invoice_id, attempt)


@pytest.mark.rule("DUNNING-002")
def test_schedule_dunning_reports_an_attempt_the_owner_already_held() -> None:
    scheduled = schedule_dunning(RacedDunningRepository(), date(2026, 2, 18))

    assert [(item.invoice.invoice_id, item.appended) for item in scheduled] == [
        (INVOICE_ONE, False),
        (INVOICE_TWO, True),
    ]


@pytest.mark.rule("DUNNING-003")
def test_suspend_overdue_suspends_active_tenants_past_the_grace_period_through_plans() -> None:
    repository = FakeDunningRepository()

    rows = suspend_overdue(repository, AS_OF)

    assert repository.suspended == [(TENANT_FIVE, AS_OF)]
    assert [(row.tenant_id, row.tenant_status, row.suspended_now) for row in rows] == [
        (TENANT_TWO, "suspended", False),
        (TENANT_FIVE, "suspended", True),
    ]
    assert [(item.status, item.suspended_on) for item in rows[1].subscriptions] == [
        ("suspended", AS_OF)
    ]


@pytest.mark.rule("DUNNING-003")
def test_suspend_overdue_ignores_invoices_inside_the_grace_period() -> None:
    repository = FakeDunningRepository()

    rows = suspend_overdue(repository, date(2026, 2, 26))  # invoice two issued 02-13 > 02-12

    assert repository.suspended == []
    assert [row.tenant_id for row in rows] == [TENANT_TWO]
    assert repository.notifications == []


@pytest.mark.rule("DUNNING-004")
def test_suspension_writes_one_notification_with_the_legacy_id_at_midnight_utc() -> None:
    repository = FakeDunningRepository()

    rows = suspend_overdue(repository, AS_OF)

    expected = NotificationRow(
        UUID("8cd558f5-d843-8d3d-be19-fb94c21ab81f"),
        TENANT_FIVE,
        "suspension",
        datetime(2026, 2, 28, tzinfo=UTC),
    )
    assert suspension_notification(TENANT_FIVE, AS_OF) == expected
    assert repository.notifications == [expected]
    assert rows[1].notifications == (expected,)
    assert rows[0].notifications == ()


@pytest.mark.rule("DUNNING-004")
def test_suspending_twice_on_the_same_day_leaves_a_single_notification() -> None:
    repository = FakeDunningRepository()
    suspend_overdue(repository, AS_OF)

    rows = suspend_overdue(repository, AS_OF)

    assert repository.suspended == [(TENANT_FIVE, AS_OF)]
    assert [row.kind for row in repository.notifications] == ["suspension"]
    assert rows[1].suspended_now is False and rows[1].tenant_status == "suspended"


@pytest.mark.rule("DUNNING-004")
def test_a_reactivated_tenant_suspended_again_the_same_day_does_not_duplicate_the_notice() -> None:
    repository = FakeDunningRepository()
    suspend_overdue(repository, AS_OF)
    repository.tenants[TENANT_FIVE] = "active"

    suspend_overdue(repository, AS_OF)

    assert len(repository.suspended) == 2
    assert len(repository.notifications) == 1


@pytest.mark.rule("DUNNING-003")
def test_suspend_overdue_never_suspends_inside_the_grace_period_at_the_start_of_the_calendar() -> (
    None
):
    repository = FakeDunningRepository()
    repository.invoices = {INVOICE_TWO: invoice(INVOICE_TWO, TENANT_FIVE, date.min)}

    assert suspend_overdue(repository, date(1, 1, 2)) == []
    assert suspend_overdue(repository, date(1, 1, 14)) == []
    assert repository.suspended == []
    assert [row.suspended_now for row in suspend_overdue(repository, date(1, 1, 15))] == [True]
