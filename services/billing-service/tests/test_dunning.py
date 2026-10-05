from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.domain import (
    DunningAttemptRow,
    InvoiceRow,
    NotificationRow,
    SubscriptionRow,
    TenantRow,
    attempt_id,
    next_attempt_date,
    overdue_accounts,
    schedule_dunning,
    suspend_overdue,
    suspension_notification_id,
)

TENANT_ONE = UUID("00000000-0000-0000-0000-000000000001")
TENANT_TWO = UUID("00000000-0000-0000-0000-000000000002")
TENANT_FIVE = UUID("00000000-0000-0000-0000-000000000005")
INVOICE_ONE = UUID("60000000-0000-0000-0000-000000000001")
INVOICE_TWO = UUID("60000000-0000-0000-0000-000000000002")
SUB_ONE = UUID("20000000-0000-0000-0000-000000000001")
SUB_TWO = UUID("20000000-0000-0000-0000-000000000002")
AS_OF = date(2026, 2, 28)


def invoice(
    invoice_id: UUID,
    tenant_id: UUID = TENANT_ONE,
    issued_at: datetime | None = None,
    status: str = "overdue",
    tenant_status: str = "active",
) -> InvoiceRow:
    return InvoiceRow(
        invoice_id=invoice_id,
        tenant_id=tenant_id,
        issued_at=issued_at or datetime(2026, 2, 1, tzinfo=UTC),
        total=Decimal("161.29"),
        status=status,
        tenant_status=tenant_status,
    )


class FakeDunningRepository:
    def __init__(
        self,
        invoices: list[InvoiceRow],
        tenants: dict[UUID, TenantRow] | None = None,
        subscriptions: list[SubscriptionRow] | None = None,
        attempts: list[DunningAttemptRow] | None = None,
        notifications: list[NotificationRow] | None = None,
    ) -> None:
        self.invoices = invoices
        self.tenants = tenants if tenants is not None else {}
        self.subscriptions = subscriptions if subscriptions is not None else []
        self.attempts = attempts if attempts is not None else []
        self.notifications = notifications if notifications is not None else []
        self.tenant_status_updates: list[tuple[UUID, str]] = []
        self.subscription_suspensions: list[tuple[UUID, date]] = []

    def list_invoices(self) -> list[InvoiceRow]:
        return list(self.invoices)

    def list_attempt_nos(self, invoice_id: UUID) -> list[int]:
        return [row.attempt_no for row in self.attempts if row.invoice_id == invoice_id]

    def insert_attempt(self, attempt: DunningAttemptRow) -> None:
        self.attempts.append(attempt)

    def get_tenant(self, tenant_id: UUID) -> TenantRow | None:
        return self.tenants.get(tenant_id)

    def update_tenant_status(self, tenant_id: UUID, status: str) -> None:
        self.tenant_status_updates.append((tenant_id, status))
        self.tenants[tenant_id] = replace(self.tenants[tenant_id], status=status)

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        return [item for item in self.subscriptions if item.tenant_id == tenant_id]

    def suspend_subscription(self, subscription_id: UUID, suspended_on: date) -> None:
        self.subscription_suspensions.append((subscription_id, suspended_on))
        self.subscriptions = [
            replace(item, status="suspended", suspended_on=suspended_on)
            if item.subscription_id == subscription_id
            else item
            for item in self.subscriptions
        ]

    def notification_exists(self, tenant_id: UUID, kind: str, sent_at: datetime) -> bool:
        return any(
            row.tenant_id == tenant_id and row.kind == kind and row.sent_at == sent_at
            for row in self.notifications
        )

    def insert_notification(self, notification: NotificationRow) -> None:
        self.notifications.append(notification)


@pytest.mark.rule("DUNNING-001")
def test_overdue_accounts_excludes_non_overdue_statuses() -> None:
    rows = overdue_accounts(
        [
            invoice(INVOICE_ONE, status="issued"),
            invoice(INVOICE_TWO, status="overdue"),
        ],
        AS_OF,
    )
    assert [row.invoice_id for row in rows] == [INVOICE_TWO]


@pytest.mark.rule("DUNNING-001")
def test_overdue_accounts_excludes_invoice_issued_on_as_of() -> None:
    rows = overdue_accounts(
        [invoice(INVOICE_ONE, issued_at=datetime(2026, 2, 28, tzinfo=UTC))],
        AS_OF,
    )
    assert rows == []


@pytest.mark.rule("DUNNING-001")
def test_overdue_accounts_includes_suspended_tenants() -> None:
    rows = overdue_accounts(
        [invoice(INVOICE_ONE, tenant_id=TENANT_TWO, tenant_status="suspended")],
        AS_OF,
    )
    assert len(rows) == 1
    assert rows[0].tenant_status == "suspended"


@pytest.mark.rule("DUNNING-001")
def test_overdue_accounts_orders_ties_on_issued_at_by_invoice_id() -> None:
    issued_at = datetime(2026, 2, 1, tzinfo=UTC)
    rows = overdue_accounts(
        [
            invoice(INVOICE_TWO, issued_at=issued_at),
            invoice(INVOICE_ONE, issued_at=issued_at),
        ],
        AS_OF,
    )
    assert [row.invoice_id for row in rows] == [INVOICE_ONE, INVOICE_TWO]


@pytest.mark.rule("DUNNING-001")
def test_overdue_accounts_derives_issue_date_in_utc() -> None:
    # 2026-02-27T23:30-05:00 is 2026-02-28 in UTC, so it is not strictly before as_of.
    offset = timezone(timedelta(hours=-5))
    rows = overdue_accounts(
        [invoice(INVOICE_ONE, issued_at=datetime(2026, 2, 27, 23, 30, tzinfo=offset))],
        AS_OF,
    )
    assert rows == []


@pytest.mark.rule("DUNNING-002")
def test_overdue_accounts_reports_days_overdue() -> None:
    rows = overdue_accounts(
        [
            invoice(INVOICE_ONE, issued_at=datetime(2026, 2, 1, tzinfo=UTC)),
            invoice(INVOICE_TWO, issued_at=datetime(2026, 2, 13, tzinfo=UTC)),
        ],
        AS_OF,
    )
    assert [row.days_overdue for row in rows] == [27, 15]


@pytest.mark.rule("DUNNING-003")
def test_schedule_dunning_counts_past_sent_attempt() -> None:
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE)],
        attempts=[
            DunningAttemptRow(UUID(int=1), TENANT_ONE, INVOICE_ONE, 1, AS_OF, "sent")
        ],
    )
    created = schedule_dunning(repository, AS_OF)
    assert [attempt.attempt_no for attempt in created] == [2]


@pytest.mark.rule("DUNNING-003")
def test_schedule_dunning_uses_max_attempt_no_of_any_status() -> None:
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE)],
        attempts=[
            DunningAttemptRow(UUID(int=1), TENANT_ONE, INVOICE_ONE, 1, AS_OF, "skipped"),
            DunningAttemptRow(UUID(int=3), TENANT_ONE, INVOICE_ONE, 3, AS_OF, "sent"),
        ],
    )
    created = schedule_dunning(repository, AS_OF)
    assert [attempt.attempt_no for attempt in created] == [4]


@pytest.mark.rule("DUNNING-003")
def test_schedule_dunning_schedules_invoice_issued_after_as_of() -> None:
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE, issued_at=datetime(2026, 3, 1, tzinfo=UTC))]
    )
    created = schedule_dunning(repository, AS_OF)
    assert [attempt.invoice_id for attempt in created] == [INVOICE_ONE]


@pytest.mark.rule("DUNNING-003")
def test_schedule_dunning_is_not_idempotent() -> None:
    repository = FakeDunningRepository([invoice(INVOICE_ONE)])
    first = schedule_dunning(repository, AS_OF)
    second = schedule_dunning(repository, AS_OF)
    assert [attempt.attempt_no for attempt in first] == [1]
    assert [attempt.attempt_no for attempt in second] == [2]


@pytest.mark.rule("DUNNING-003")
def test_schedule_dunning_schedules_suspended_tenants_invoice() -> None:
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE, tenant_id=TENANT_TWO, tenant_status="suspended")]
    )
    created = schedule_dunning(repository, AS_OF)
    assert [attempt.tenant_id for attempt in created] == [TENANT_TWO]


@pytest.mark.rule("DUNNING-004")
@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        (date(2026, 2, 14), date(2026, 2, 16)),
        (date(2026, 2, 15), date(2026, 2, 16)),
        (date(2026, 2, 17), date(2026, 2, 17)),
    ],
)
def test_next_attempt_date_skips_weekends(as_of: date, expected: date) -> None:
    assert next_attempt_date(as_of) == expected


@pytest.mark.rule("DUNNING-005")
def test_attempt_id_matches_md5_uuid_derivation() -> None:
    expected = UUID(
        hashlib.md5(b"60000000-0000-0000-0000-0000000000011").hexdigest()
    )
    assert attempt_id(INVOICE_ONE, 1) == expected


@pytest.mark.rule("DUNNING-005")
def test_schedule_dunning_inserts_scheduled_attempt_with_invoice_tenant() -> None:
    repository = FakeDunningRepository([invoice(INVOICE_ONE, tenant_id=TENANT_TWO)])
    created = schedule_dunning(repository, AS_OF)
    assert created[0].status == "scheduled"
    assert created[0].tenant_id == TENANT_TWO
    assert repository.attempts == created


@pytest.mark.rule("DUNNING-006")
def test_suspend_overdue_suspends_invoice_issued_exactly_threshold_days_ago() -> None:
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE, issued_at=datetime(2026, 2, 14, tzinfo=UTC))],
        tenants={TENANT_ONE: TenantRow(TENANT_ONE, "active")},
    )
    assert suspend_overdue(repository, AS_OF) == [TENANT_ONE]
    assert repository.tenants[TENANT_ONE].status == "suspended"


@pytest.mark.rule("DUNNING-006")
def test_suspend_overdue_ignores_invoice_inside_threshold() -> None:
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE, issued_at=datetime(2026, 2, 15, tzinfo=UTC))],
        tenants={TENANT_ONE: TenantRow(TENANT_ONE, "active")},
    )
    assert suspend_overdue(repository, AS_OF) == []
    assert repository.tenants[TENANT_ONE].status == "active"


@pytest.mark.rule("DUNNING-006")
def test_suspend_overdue_skips_already_suspended_tenant() -> None:
    subscription = SubscriptionRow(
        SUB_ONE, TENANT_ONE, UUID(int=9), date(2026, 1, 1), None, "active", None
    )
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE)],
        tenants={TENANT_ONE: TenantRow(TENANT_ONE, "suspended")},
        subscriptions=[subscription],
    )
    assert suspend_overdue(repository, AS_OF) == []
    assert repository.subscription_suspensions == []
    assert repository.notifications == []


@pytest.mark.rule("DUNNING-006")
def test_suspend_overdue_second_run_is_noop() -> None:
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE)],
        tenants={TENANT_ONE: TenantRow(TENANT_ONE, "active")},
    )
    suspend_overdue(repository, AS_OF)
    assert suspend_overdue(repository, AS_OF) == []
    assert repository.tenant_status_updates == [(TENANT_ONE, "suspended")]


@pytest.mark.rule("DUNNING-007")
def test_suspend_overdue_suspends_only_active_subscriptions() -> None:
    active = SubscriptionRow(
        SUB_ONE, TENANT_ONE, UUID(int=9), date(2026, 1, 1), None, "active", None
    )
    cancelled = SubscriptionRow(
        SUB_TWO, TENANT_ONE, UUID(int=9), date(2026, 1, 1), date(2026, 2, 10),
        "cancelled", None,
    )
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE)],
        tenants={TENANT_ONE: TenantRow(TENANT_ONE, "active")},
        subscriptions=[active, cancelled],
    )
    suspend_overdue(repository, AS_OF)
    assert repository.subscription_suspensions == [(SUB_ONE, AS_OF)]
    updated = {item.subscription_id: item for item in repository.subscriptions}
    assert updated[SUB_ONE].status == "suspended"
    assert updated[SUB_ONE].suspended_on == AS_OF
    assert updated[SUB_TWO].status == "cancelled"
    assert updated[SUB_TWO].suspended_on is None


@pytest.mark.rule("DUNNING-008")
def test_suspension_notification_id_matches_legacy_value() -> None:
    assert suspension_notification_id(TENANT_FIVE, AS_OF) == UUID(
        "8cd558f5-d843-8d3d-be19-fb94c21ab81f"
    )


@pytest.mark.rule("DUNNING-008")
def test_suspend_overdue_inserts_notification_at_utc_midnight() -> None:
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE)],
        tenants={TENANT_ONE: TenantRow(TENANT_ONE, "active")},
    )
    suspend_overdue(repository, AS_OF)
    [notification] = repository.notifications
    assert notification.kind == "suspension"
    assert notification.sent_at == datetime(2026, 2, 28, tzinfo=UTC)
    assert notification.notification_id == suspension_notification_id(TENANT_ONE, AS_OF)


@pytest.mark.rule("DUNNING-008")
def test_suspend_overdue_does_not_duplicate_existing_notification() -> None:
    existing = NotificationRow(
        UUID(int=1), TENANT_ONE, "suspension", datetime(2026, 2, 28, tzinfo=UTC)
    )
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE)],
        tenants={TENANT_ONE: TenantRow(TENANT_ONE, "active")},
        notifications=[existing],
    )
    suspend_overdue(repository, AS_OF)
    assert repository.notifications == [existing]


@pytest.mark.rule("DUNNING-008")
def test_suspend_overdue_twice_leaves_one_notification() -> None:
    repository = FakeDunningRepository(
        [invoice(INVOICE_ONE)],
        tenants={TENANT_ONE: TenantRow(TENANT_ONE, "active")},
    )
    suspend_overdue(repository, AS_OF)
    suspend_overdue(repository, AS_OF)
    assert len(repository.notifications) == 1
