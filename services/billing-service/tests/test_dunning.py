from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.domain import (
    DunningAttemptRow,
    InvoiceRow,
    NotificationRow,
    SubscriptionRow,
    SuspensionConflictError,
    TenantRow,
    md5_uuid,
    next_business_day,
    overdue_accounts,
    schedule_dunning,
    sorted_attempts,
    suspend_overdue,
    suspension_notifications,
)

TENANT_TWO = UUID("00000000-0000-0000-0000-000000000002")
TENANT_FIVE = UUID("00000000-0000-0000-0000-000000000005")
TENANT_SIX = UUID("00000000-0000-0000-0000-000000000006")
INVOICE_ONE = UUID("60000000-0000-0000-0000-000000000001")
INVOICE_TWO = UUID("60000000-0000-0000-0000-000000000002")
INVOICE_THREE = UUID("60000000-0000-0000-0000-000000000003")
PLAN = UUID("10000000-0000-0000-0000-000000000002")


def invoice(invoice_id: UUID, tenant_id: UUID, issued_at: datetime, status: str) -> InvoiceRow:
    return InvoiceRow(invoice_id, tenant_id, issued_at, Decimal("161.29"), status)


def subscription(
    number: int, tenant_id: UUID, status: str = "active", starts_on: date = date(2026, 1, 1)
) -> SubscriptionRow:
    return SubscriptionRow(
        UUID(f"20000000-0000-0000-0000-{number:012d}"),
        tenant_id,
        PLAN,
        starts_on,
        None,
        status,
        None,
    )


def seed_invoices() -> list[InvoiceRow]:
    return [
        invoice(INVOICE_THREE, TENANT_SIX, datetime(2026, 2, 28, tzinfo=UTC), "issued"),
        invoice(INVOICE_TWO, TENANT_FIVE, datetime(2026, 2, 13, tzinfo=UTC), "overdue"),
        invoice(INVOICE_ONE, TENANT_TWO, datetime(2026, 2, 1, tzinfo=UTC), "overdue"),
    ]


def seed_tenants() -> list[TenantRow]:
    return [
        TenantRow(TENANT_TWO, "suspended"),
        TenantRow(TENANT_FIVE, "active"),
        TenantRow(TENANT_SIX, "active"),
    ]


class FakeDunningRepository:
    def __init__(
        self,
        invoices: list[InvoiceRow] | None = None,
        tenants: list[TenantRow] | None = None,
        attempts: list[DunningAttemptRow] | None = None,
        subscriptions: list[SubscriptionRow] | None = None,
        notifications: list[NotificationRow] | None = None,
    ) -> None:
        self.invoices = seed_invoices() if invoices is None else invoices
        self.tenants = seed_tenants() if tenants is None else tenants
        self.attempts = (
            [
                DunningAttemptRow(
                    UUID("80000000-0000-0000-0000-000000000001"),
                    TENANT_FIVE,
                    INVOICE_TWO,
                    1,
                    date(2026, 2, 16),
                    "sent",
                )
            ]
            if attempts is None
            else attempts
        )
        self.subscriptions = (
            [
                subscription(2, TENANT_TWO, "suspended"),
                subscription(5, TENANT_FIVE),
                subscription(6, TENANT_SIX),
            ]
            if subscriptions is None
            else subscriptions
        )
        self.notifications = (
            [
                NotificationRow(
                    UUID("90000000-0000-0000-0000-000000000001"),
                    TENANT_FIVE,
                    "dunning",
                    datetime(2026, 2, 16, 9, tzinfo=UTC),
                )
            ]
            if notifications is None
            else notifications
        )

    def list_invoices(self) -> list[InvoiceRow]:
        return list(self.invoices)

    def list_tenants(self) -> list[TenantRow]:
        return list(self.tenants)

    def list_attempts(self) -> list[DunningAttemptRow]:
        return list(self.attempts)

    def insert_attempt(self, attempt: DunningAttemptRow) -> None:
        assert all(
            (item.invoice_id, item.attempt_no) != (attempt.invoice_id, attempt.attempt_no)
            for item in self.attempts
        )
        self.attempts.append(attempt)

    def update_tenant_status(self, tenant_id: UUID, status: str) -> None:
        self.tenants = [
            replace(item, status=status) if item.tenant_id == tenant_id else item
            for item in self.tenants
        ]

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        return [item for item in self.subscriptions if item.tenant_id == tenant_id]

    def suspend_subscription(self, subscription_id: UUID, suspended_on: date) -> None:
        self.subscriptions = [
            replace(item, status="suspended", suspended_on=suspended_on)
            if item.subscription_id == subscription_id
            else item
            for item in self.subscriptions
        ]

    def list_notifications(self) -> list[NotificationRow]:
        return list(self.notifications)

    def insert_notification(self, notification: NotificationRow) -> None:
        self.notifications.append(notification)


def tenant_status(repository: FakeDunningRepository, tenant_id: UUID) -> str:
    return next(item.status for item in repository.tenants if item.tenant_id == tenant_id)


@pytest.mark.rule("DUNNING-R01")
def test_overdue_accounts_lists_overdue_invoices_in_issue_order() -> None:
    accounts = overdue_accounts(seed_invoices(), seed_tenants(), date(2026, 2, 28))

    assert [item.tenant_id for item in accounts] == [TENANT_TWO, TENANT_FIVE]
    assert [item.tenant_status for item in accounts] == ["suspended", "active"]
    assert accounts[0].total == Decimal("161.29")


@pytest.mark.rule("DUNNING-R01")
def test_overdue_accounts_excludes_invoices_issued_on_as_of() -> None:
    assert overdue_accounts(seed_invoices(), seed_tenants(), date(2026, 2, 1)) == []
    accounts = overdue_accounts(seed_invoices(), seed_tenants(), date(2026, 2, 2))
    assert [item.invoice_id for item in accounts] == [INVOICE_ONE]


@pytest.mark.rule("DUNNING-R01")
def test_overdue_accounts_breaks_issue_time_ties_by_invoice_id() -> None:
    issued = datetime(2026, 2, 1, tzinfo=UTC)
    invoices = [
        invoice(INVOICE_TWO, TENANT_FIVE, issued, "overdue"),
        invoice(INVOICE_ONE, TENANT_TWO, issued, "overdue"),
    ]
    accounts = overdue_accounts(invoices, seed_tenants(), date(2026, 2, 10))
    assert [item.invoice_id for item in accounts] == [INVOICE_ONE, INVOICE_TWO]


@pytest.mark.rule("DUNNING-R02")
def test_days_overdue_counts_days_since_issue() -> None:
    accounts = overdue_accounts(seed_invoices(), seed_tenants(), date(2026, 2, 28))
    assert [item.days_overdue for item in accounts] == [27, 15]


@pytest.mark.rule("DUNNING-R02")
def test_days_overdue_uses_the_utc_issue_date() -> None:
    eastern = timezone(timedelta(hours=-5))
    late_evening = datetime(2026, 2, 1, 23, 30, tzinfo=eastern)
    invoices = [invoice(INVOICE_ONE, TENANT_TWO, late_evening, "overdue")]

    assert overdue_accounts(invoices, seed_tenants(), date(2026, 2, 2)) == []
    accounts = overdue_accounts(invoices, seed_tenants(), date(2026, 2, 3))
    assert [item.days_overdue for item in accounts] == [1]


@pytest.mark.rule("DUNNING-R03")
def test_schedule_covers_every_overdue_invoice_regardless_of_tenant_status() -> None:
    repository = FakeDunningRepository()
    created = schedule_dunning(repository, date(2026, 2, 17))

    assert [item.invoice_id for item in created] == [INVOICE_ONE, INVOICE_TWO]
    assert INVOICE_THREE not in {item.invoice_id for item in repository.attempts}


@pytest.mark.rule("DUNNING-R03")
def test_schedule_ignores_issue_date_after_as_of() -> None:
    repository = FakeDunningRepository()
    created = schedule_dunning(repository, date(2026, 1, 5))

    assert [(item.invoice_id, item.scheduled_for) for item in created] == [
        (INVOICE_ONE, date(2026, 1, 5)),
        (INVOICE_TWO, date(2026, 1, 5)),
    ]


@pytest.mark.rule("DUNNING-R04")
def test_schedule_appends_next_attempt_with_md5_id() -> None:
    repository = FakeDunningRepository()
    created = schedule_dunning(repository, date(2026, 2, 17))

    assert [(item.invoice_id, item.attempt_no, item.status) for item in created] == [
        (INVOICE_ONE, 1, "scheduled"),
        (INVOICE_TWO, 2, "scheduled"),
    ]
    assert created[1].attempt_id == UUID("6118c817-d22e-6eb3-832a-96f21a646a7a")
    assert created[0].attempt_id == md5_uuid(f"{INVOICE_ONE}1")
    assert repository.attempts[0].status == "sent"
    assert repository.attempts[0].scheduled_for == date(2026, 2, 16)


@pytest.mark.rule("DUNNING-R04")
def test_schedule_appends_again_on_every_run() -> None:
    repository = FakeDunningRepository()
    schedule_dunning(repository, date(2026, 2, 17))
    schedule_dunning(repository, date(2026, 2, 18))

    rows = [
        (item.invoice_id, item.attempt_no, item.status)
        for item in sorted_attempts(repository.attempts)
    ]
    assert rows == [
        (INVOICE_ONE, 1, "scheduled"),
        (INVOICE_ONE, 2, "scheduled"),
        (INVOICE_TWO, 1, "sent"),
        (INVOICE_TWO, 2, "scheduled"),
        (INVOICE_TWO, 3, "scheduled"),
    ]


@pytest.mark.rule("DUNNING-R04")
def test_schedule_numbers_after_the_highest_attempt_even_with_gaps() -> None:
    attempts = [
        DunningAttemptRow(md5_uuid("gap"), TENANT_TWO, INVOICE_ONE, 3, date(2026, 2, 2), "skipped")
    ]
    repository = FakeDunningRepository(attempts=attempts)
    created = schedule_dunning(repository, date(2026, 2, 17))
    assert created[0].attempt_no == 4


@pytest.mark.rule("DUNNING-R05")
@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        (date(2026, 2, 13), date(2026, 2, 13)),
        (date(2026, 2, 14), date(2026, 2, 16)),
        (date(2026, 2, 15), date(2026, 2, 16)),
        (date(2026, 2, 16), date(2026, 2, 16)),
        (date(2026, 2, 17), date(2026, 2, 17)),
        (date(2026, 2, 28), date(2026, 3, 2)),
    ],
)
def test_weekend_moves_to_monday(as_of: date, expected: date) -> None:
    assert next_business_day(as_of) == expected


@pytest.mark.rule("DUNNING-R05")
def test_schedule_uses_the_shifted_date_for_every_attempt() -> None:
    repository = FakeDunningRepository()
    created = schedule_dunning(repository, date(2026, 2, 14))
    assert {item.scheduled_for for item in created} == {date(2026, 2, 16)}


@pytest.mark.rule("DUNNING-R06")
def test_suspension_suspends_active_tenant_and_active_subscriptions() -> None:
    repository = FakeDunningRepository()
    result = suspend_overdue(repository, date(2026, 2, 28))

    assert result.suspended_tenants == [TENANT_FIVE]
    assert tenant_status(repository, TENANT_FIVE) == "suspended"
    suspended = repository.list_subscriptions(TENANT_FIVE)[0]
    assert (suspended.status, suspended.suspended_on) == ("suspended", date(2026, 2, 28))
    assert [(item.status, item.suspended_on) for item in result.suspended_subscriptions] == [
        ("suspended", date(2026, 2, 28))
    ]
    untouched = repository.list_subscriptions(TENANT_TWO)[0]
    assert untouched.suspended_on is None
    assert tenant_status(repository, TENANT_SIX) == "active"


@pytest.mark.rule("DUNNING-R06")
def test_suspension_threshold_is_inclusive_at_fourteen_days() -> None:
    on_threshold = FakeDunningRepository()
    assert suspend_overdue(on_threshold, date(2026, 2, 27)).suspended_tenants == [TENANT_FIVE]

    before_threshold = FakeDunningRepository()
    assert suspend_overdue(before_threshold, date(2026, 2, 26)).suspended_tenants == []
    assert tenant_status(before_threshold, TENANT_FIVE) == "active"


@pytest.mark.rule("DUNNING-R06")
def test_suspension_selects_subscriptions_by_status_only() -> None:
    ended = replace(subscription(5, TENANT_FIVE), ends_on=date(2026, 1, 31))
    cancelled = subscription(7, TENANT_FIVE, "cancelled")
    repository = FakeDunningRepository(subscriptions=[ended, cancelled])
    result = suspend_overdue(repository, date(2026, 2, 28))

    assert [item.subscription_id for item in result.suspended_subscriptions] == [
        ended.subscription_id
    ]
    assert repository.list_subscriptions(TENANT_FIVE)[1].status == "cancelled"


@pytest.mark.rule("DUNNING-R06")
def test_suspension_conflicts_on_a_subscription_starting_after_as_of() -> None:
    future = subscription(5, TENANT_FIVE, starts_on=date(2026, 3, 1))
    repository = FakeDunningRepository(subscriptions=[future])
    with pytest.raises(SuspensionConflictError):
        suspend_overdue(repository, date(2026, 2, 28))


@pytest.mark.rule("DUNNING-R07")
def test_suspension_notification_uses_md5_id_and_utc_midnight() -> None:
    repository = FakeDunningRepository()
    result = suspend_overdue(repository, date(2026, 2, 28))

    assert [
        (item.notification_id, item.tenant_id, item.kind, item.sent_at)
        for item in result.notifications
    ] == [
        (
            UUID("8cd558f5-d843-8d3d-be19-fb94c21ab81f"),
            TENANT_FIVE,
            "suspension",
            datetime(2026, 2, 28, tzinfo=UTC),
        )
    ]
    kinds = [item.kind for item in suspension_notifications(repository.notifications)]
    assert kinds == ["suspension"]


@pytest.mark.rule("DUNNING-R07")
def test_second_suspension_run_changes_nothing() -> None:
    repository = FakeDunningRepository()
    suspend_overdue(repository, date(2026, 2, 28))
    snapshot = (list(repository.tenants), list(repository.subscriptions))
    second = suspend_overdue(repository, date(2026, 2, 28))

    assert second.suspended_tenants == []
    assert second.notifications == []
    assert (repository.tenants, repository.subscriptions) == snapshot
    assert len(suspension_notifications(repository.notifications)) == 1


@pytest.mark.rule("DUNNING-R07")
def test_existing_suspension_notification_is_not_duplicated() -> None:
    existing = NotificationRow(
        md5_uuid("existing"), TENANT_FIVE, "suspension", datetime(2026, 2, 28, tzinfo=UTC)
    )
    repository = FakeDunningRepository(notifications=[existing])
    result = suspend_overdue(repository, date(2026, 2, 28))

    assert result.suspended_tenants == [TENANT_FIVE]
    assert result.notifications == []
    assert repository.notifications == [existing]


@pytest.mark.rule("DUNNING-R07")
def test_already_suspended_tenant_gets_no_notification() -> None:
    repository = FakeDunningRepository()
    suspend_overdue(repository, date(2026, 3, 31))
    tenants = {item.tenant_id for item in suspension_notifications(repository.notifications)}
    assert tenants == {TENANT_FIVE}


class FakeConnection:
    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_suspension_conflict_returns_409(monkeypatch) -> None:
    def conflict(*_args: object) -> None:
        raise SuspensionConflictError("starts later")

    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "suspend_overdue", conflict)
    with TestClient(main.app) as client:
        response = client.post("/api/dunning/suspend", json={"as_of": "2026-02-28"})

    assert response.status_code == 409


def test_schedule_and_suspend_responses_expose_contract_fields(monkeypatch) -> None:
    repository = FakeDunningRepository()
    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "PostgresDunningRepository", lambda _connection: repository)
    with TestClient(main.app) as client:
        overdue = client.get("/api/dunning/overdue", params={"as_of": "2026-02-28"}).json()
        schedule = client.post("/api/dunning/schedule", json={"as_of": "2026-02-14"}).json()
        suspend = client.post("/api/dunning/suspend", json={"as_of": "2026-02-28"}).json()

    assert [item["days_overdue"] for item in overdue] == [27, 15]
    assert overdue[0]["total"] == "161.29"
    assert schedule["last_scheduled"] == {
        "invoice_id": str(INVOICE_TWO),
        "attempt_no": 2,
        "scheduled_for": "2026-02-16",
        "status": "scheduled",
    }
    assert [row["attempt_no"] for row in schedule["attempts"]] == [1, 1, 2]
    assert suspend["suspended_subscriptions"][0]["suspended_on"] == "2026-02-28"
    assert suspend["notifications"] == [
        {
            "id": "8cd558f5-d843-8d3d-be19-fb94c21ab81f",
            "tenant_id": str(TENANT_FIVE),
            "kind": "suspension",
            "sent_at": "2026-02-28T00:00:00Z",
        }
    ]
