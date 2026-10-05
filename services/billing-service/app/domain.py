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


# --- dunning ---


@dataclass(frozen=True)
class DunningInvoiceRow:
    invoice_id: UUID
    tenant_id: UUID
    issued_at: datetime
    total: Decimal
    status: str
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


@dataclass(frozen=True)
class OverdueAccount:
    tenant_id: UUID
    invoice_id: UUID
    total: Decimal
    days_overdue: int
    tenant_status: str


class DunningRepository(Protocol):
    def list_dunning_invoices(self) -> list[DunningInvoiceRow]: ...

    def max_attempt_no(self, invoice_id: UUID) -> int: ...

    def insert_dunning_attempt(self, attempt: DunningAttemptRow) -> bool: ...

    def list_dunning_attempts(self) -> list[DunningAttemptRow]: ...

    def tenant_status(self, tenant_id: UUID) -> str | None: ...

    def suspend_tenant(self, tenant_id: UUID) -> None: ...

    def suspend_active_subscriptions(self, tenant_id: UUID, on: date) -> list[SubscriptionRow]: ...

    def suspension_notification_exists(self, tenant_id: UUID, sent_at: datetime) -> bool: ...

    def insert_notification(self, notification: NotificationRow) -> None: ...

    def list_suspension_notifications(self) -> list[NotificationRow]: ...


SUSPENSION_GRACE_DAYS = 14


def issue_date(issued_at: datetime) -> date:
    return issued_at.astimezone(UTC).date()


def overdue_accounts(invoices: list[DunningInvoiceRow], as_of: date) -> list[OverdueAccount]:
    overdue = [
        invoice
        for invoice in invoices
        if invoice.status == "overdue" and issue_date(invoice.issued_at) < as_of
    ]
    return [
        OverdueAccount(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.invoice_id,
            total=invoice.total,
            days_overdue=(as_of - issue_date(invoice.issued_at)).days,
            tenant_status=invoice.tenant_status,
        )
        for invoice in sorted(overdue, key=lambda item: (item.issued_at, item.invoice_id))
    ]


def dunning_schedule_date(as_of: date) -> date:
    if as_of.isoweekday() == 6:
        return as_of + timedelta(days=2)
    if as_of.isoweekday() == 7:
        return as_of + timedelta(days=1)
    return as_of


def dunning_attempt_id(invoice_id: UUID, attempt_no: int) -> UUID:
    value = hashlib.md5(f"{invoice_id}{attempt_no}".encode()).hexdigest()
    return UUID(value)


def schedule_dunning(repository: DunningRepository, as_of: date) -> list[DunningAttemptRow]:
    created = []
    for invoice in sorted(
        (item for item in repository.list_dunning_invoices() if item.status == "overdue"),
        key=lambda item: (item.issued_at, item.invoice_id),
    ):
        attempt_no = repository.max_attempt_no(invoice.invoice_id) + 1
        attempt = DunningAttemptRow(
            attempt_id=dunning_attempt_id(invoice.invoice_id, attempt_no),
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.invoice_id,
            attempt_no=attempt_no,
            scheduled_for=dunning_schedule_date(as_of),
            status="scheduled",
        )
        if repository.insert_dunning_attempt(attempt):
            created.append(attempt)
    return created


def suspension_notification_id(tenant_id: UUID, as_of: date) -> UUID:
    value = hashlib.md5(f"{tenant_id}suspension{as_of.isoformat()}".encode()).hexdigest()
    return UUID(value)


def suspend_overdue(repository: DunningRepository, as_of: date) -> list[SubscriptionRow]:
    cutoff = as_of - timedelta(days=SUSPENSION_GRACE_DAYS)
    tenant_ids = sorted(
        {
            invoice.tenant_id
            for invoice in repository.list_dunning_invoices()
            if invoice.status == "overdue" and issue_date(invoice.issued_at) <= cutoff
        }
    )
    sent_at = datetime.combine(as_of, time(0), tzinfo=UTC)
    suspended = []
    for tenant_id in tenant_ids:
        if repository.tenant_status(tenant_id) != "active":
            continue
        repository.suspend_tenant(tenant_id)
        suspended.extend(repository.suspend_active_subscriptions(tenant_id, as_of))
        if not repository.suspension_notification_exists(tenant_id, sent_at):
            repository.insert_notification(
                NotificationRow(
                    notification_id=suspension_notification_id(tenant_id, as_of),
                    tenant_id=tenant_id,
                    kind="suspension",
                    sent_at=sent_at,
                )
            )
    return sorted(suspended, key=lambda item: (item.tenant_id, item.subscription_id))
