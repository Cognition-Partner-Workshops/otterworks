from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid5

PLAN_CHANGE_NAMESPACE = UUID("d8e9df63-6e46-4d6a-b9c2-2ef6e99cb5ee")


@dataclass(frozen=True)
class PlanRow:
    plan_id: UUID
    code: str
    tier: str
    monthly_fee: Decimal
    included_units: int
    overage_rate: Decimal
    active: bool


@dataclass(frozen=True)
class SubscriptionRow:
    subscription_id: UUID
    tenant_id: UUID
    plan_id: UUID
    starts_on: date
    ends_on: date | None
    status: str
    suspended_on: date | None


@dataclass(frozen=True)
class EntitlementRow:
    tenant_id: UUID
    plan_code: str
    tier: str
    monthly_fee: Decimal
    included_units: int
    subscription_status: str
    ends_on: date | None
    starts_on: date


@dataclass(frozen=True)
class TenantRow:
    tenant_id: UUID
    status: str


@dataclass(frozen=True)
class InvoiceRow:
    invoice_id: UUID
    tenant_id: UUID
    issued_at: datetime
    total: Decimal
    status: str
    tenant_status: str


@dataclass(frozen=True)
class OverdueAccountRow:
    tenant_id: UUID
    invoice_id: UUID
    issued_at: datetime
    total: Decimal
    days_overdue: int
    tenant_status: str


@dataclass(frozen=True)
class DunningAttemptRow:
    attempt_id: UUID
    tenant_id: UUID
    invoice_id: UUID
    attempt_no: int
    scheduled_for: date
    status: str


@dataclass(frozen=True)
class NotificationRow:
    notification_id: UUID
    tenant_id: UUID
    kind: str
    sent_at: datetime


class PlansRepository(Protocol):
    def list_plans(self) -> list[PlanRow]: ...

    def find_entitlements(self, tenant_id: UUID) -> list[EntitlementRow]: ...

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...

    def update_subscription(self, subscription_id: UUID, ends_on: date, status: str) -> None: ...

    def insert_subscription(
        self,
        subscription_id: UUID,
        tenant_id: UUID,
        plan_id: UUID,
        starts_on: date,
        status: str,
    ) -> None: ...


class DunningRepository(Protocol):
    def list_invoices(self) -> list[InvoiceRow]: ...

    def list_attempt_nos(self, invoice_id: UUID) -> list[int]: ...

    def insert_attempt(self, attempt: DunningAttemptRow) -> None: ...

    def get_tenant(self, tenant_id: UUID) -> TenantRow | None: ...

    def update_tenant_status(self, tenant_id: UUID, status: str) -> None: ...

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...

    def suspend_subscription(self, subscription_id: UUID, suspended_on: date) -> None: ...

    def notification_exists(self, tenant_id: UUID, kind: str, sent_at: datetime) -> bool: ...

    def insert_notification(self, notification: NotificationRow) -> None: ...


def utc_issue_date(issued_at: datetime) -> date:
    return issued_at.astimezone(UTC).date()


def overdue_accounts(invoices: list[InvoiceRow], as_of: date) -> list[OverdueAccountRow]:
    rows = []
    for invoice in invoices:
        if invoice.status != "overdue":
            continue
        issue_date = utc_issue_date(invoice.issued_at)
        if issue_date >= as_of:
            continue
        rows.append(
            OverdueAccountRow(
                tenant_id=invoice.tenant_id,
                invoice_id=invoice.invoice_id,
                issued_at=invoice.issued_at,
                total=invoice.total,
                days_overdue=(as_of - issue_date).days,
                tenant_status=invoice.tenant_status,
            )
        )
    return sorted(rows, key=lambda row: (row.issued_at, row.invoice_id))


def next_attempt_date(as_of: date) -> date:
    weekday = as_of.isoweekday()
    if weekday == 6:
        return as_of + timedelta(days=2)
    if weekday == 7:
        return as_of + timedelta(days=1)
    return as_of


def attempt_id(invoice_id: UUID, attempt_no: int) -> UUID:
    return UUID(hashlib.md5(f"{invoice_id}{attempt_no}".encode()).hexdigest())


def schedule_dunning(repository: DunningRepository, as_of: date) -> list[DunningAttemptRow]:
    invoices = sorted(
        (invoice for invoice in repository.list_invoices() if invoice.status == "overdue"),
        key=lambda invoice: (invoice.issued_at, invoice.invoice_id),
    )
    scheduled_for = next_attempt_date(as_of)
    created = []
    for invoice in invoices:
        existing = repository.list_attempt_nos(invoice.invoice_id)
        attempt_no = max(existing, default=0) + 1
        attempt = DunningAttemptRow(
            attempt_id=attempt_id(invoice.invoice_id, attempt_no),
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.invoice_id,
            attempt_no=attempt_no,
            scheduled_for=scheduled_for,
            status="scheduled",
        )
        repository.insert_attempt(attempt)
        created.append(attempt)
    return created


def suspension_notification_id(tenant_id: UUID, as_of: date) -> UUID:
    return UUID(
        hashlib.md5(f"{tenant_id}suspension{as_of.isoformat()}".encode()).hexdigest()
    )


def suspend_overdue(repository: DunningRepository, as_of: date) -> list[UUID]:
    threshold = as_of - timedelta(days=14)
    tenant_ids = sorted(
        {
            invoice.tenant_id
            for invoice in repository.list_invoices()
            if invoice.status == "overdue" and utc_issue_date(invoice.issued_at) <= threshold
        }
    )
    suspended = []
    for tenant_id in tenant_ids:
        tenant = repository.get_tenant(tenant_id)
        if tenant is None or tenant.status != "active":
            continue
        repository.update_tenant_status(tenant_id, "suspended")
        for subscription in repository.list_subscriptions(tenant_id):
            if subscription.status == "active":
                repository.suspend_subscription(subscription.subscription_id, as_of)
        sent_at = datetime.combine(as_of, time.min, tzinfo=UTC)
        if not repository.notification_exists(tenant_id, "suspension", sent_at):
            repository.insert_notification(
                NotificationRow(
                    notification_id=suspension_notification_id(tenant_id, as_of),
                    tenant_id=tenant_id,
                    kind="suspension",
                    sent_at=sent_at,
                )
            )
        suspended.append(tenant_id)
    return suspended


def catalog(plans: list[PlanRow]) -> list[PlanRow]:
    return sorted(
        (plan for plan in plans if plan.active),
        key=lambda plan: (plan.monthly_fee, plan.code),
    )


def entitlement(rows: list[EntitlementRow], tenant_id: UUID, on: date) -> EntitlementRow | None:
    eligible = [
        row
        for row in rows
        if row.tenant_id == tenant_id
        and row.starts_on <= on
        and (row.ends_on is None or row.ends_on >= on)
    ]
    return max(eligible, key=lambda row: row.starts_on, default=None)


def change_plan(
    repository: PlansRepository,
    tenant_id: UUID,
    plan_id: UUID,
    effective_on: date,
) -> tuple[list[SubscriptionRow], SubscriptionRow]:
    subscriptions = repository.list_subscriptions(tenant_id)
    for subscription in subscriptions:
        if subscription.ends_on is None and subscription.starts_on < effective_on:
            next_status = (
                subscription.status if subscription.status == "cancelled" else "active"
            )
            repository.update_subscription(
                subscription.subscription_id,
                effective_on - timedelta(days=1),
                next_status,
            )
    created_id = uuid5(PLAN_CHANGE_NAMESPACE, f"{tenant_id}{plan_id}{effective_on.isoformat()}")
    repository.insert_subscription(
        created_id,
        tenant_id,
        plan_id,
        effective_on,
        "active",
    )
    subscriptions = sorted(
        repository.list_subscriptions(tenant_id), key=lambda item: item.starts_on
    )
    created = next(item for item in subscriptions if item.subscription_id == created_id)
    return subscriptions, created
