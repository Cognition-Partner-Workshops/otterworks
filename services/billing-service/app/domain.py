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


SUSPENSION_GRACE_DAYS = 14


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


@dataclass(frozen=True)
class OverdueAccount:
    tenant_id: UUID
    invoice_id: UUID
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


@dataclass(frozen=True)
class SuspensionResult:
    suspended_tenants: list[UUID]
    suspended_subscriptions: list[SubscriptionRow]
    notifications: list[NotificationRow]


class SuspensionConflictError(Exception):
    """A subscription cannot be suspended before it starts."""


class DunningRepository(Protocol):
    def list_invoices(self) -> list[InvoiceRow]: ...

    def list_tenants(self) -> list[TenantRow]: ...

    def list_attempts(self) -> list[DunningAttemptRow]: ...

    def insert_attempt(self, attempt: DunningAttemptRow) -> None: ...

    def update_tenant_status(self, tenant_id: UUID, status: str) -> None: ...

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...

    def suspend_subscription(self, subscription_id: UUID, suspended_on: date) -> None: ...

    def list_notifications(self) -> list[NotificationRow]: ...

    def insert_notification(self, notification: NotificationRow) -> None: ...


def md5_uuid(text: str) -> UUID:
    return UUID(hashlib.md5(text.encode(), usedforsecurity=False).hexdigest())


def utc_date(value: datetime) -> date:
    return value.astimezone(UTC).date()


def _overdue_in_issue_order(invoices: list[InvoiceRow]) -> list[InvoiceRow]:
    return sorted(
        (invoice for invoice in invoices if invoice.status == "overdue"),
        key=lambda invoice: (invoice.issued_at, invoice.invoice_id),
    )


def overdue_accounts(
    invoices: list[InvoiceRow], tenants: list[TenantRow], as_of: date
) -> list[OverdueAccount]:
    tenant_status = {tenant.tenant_id: tenant.status for tenant in tenants}
    return [
        OverdueAccount(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.invoice_id,
            total=invoice.total,
            days_overdue=(as_of - utc_date(invoice.issued_at)).days,
            tenant_status=tenant_status[invoice.tenant_id],
        )
        for invoice in _overdue_in_issue_order(invoices)
        if utc_date(invoice.issued_at) < as_of and invoice.tenant_id in tenant_status
    ]


def next_business_day(as_of: date) -> date:
    weekday = as_of.isoweekday()
    if weekday == 6:
        return as_of + timedelta(days=2)
    if weekday == 7:
        return as_of + timedelta(days=1)
    return as_of


def schedule_dunning(repository: DunningRepository, as_of: date) -> list[DunningAttemptRow]:
    attempts = repository.list_attempts()
    scheduled_for = next_business_day(as_of)
    created = []
    for invoice in _overdue_in_issue_order(repository.list_invoices()):
        existing = {a.attempt_no for a in attempts if a.invoice_id == invoice.invoice_id}
        attempt_no = max(existing, default=0) + 1
        attempt = DunningAttemptRow(
            attempt_id=md5_uuid(f"{invoice.invoice_id}{attempt_no}"),
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.invoice_id,
            attempt_no=attempt_no,
            scheduled_for=scheduled_for,
            status="scheduled",
        )
        repository.insert_attempt(attempt)
        attempts.append(attempt)
        created.append(attempt)
    return created


def sorted_attempts(attempts: list[DunningAttemptRow]) -> list[DunningAttemptRow]:
    return sorted(attempts, key=lambda attempt: (attempt.invoice_id, attempt.attempt_no))


def suspension_notifications(notifications: list[NotificationRow]) -> list[NotificationRow]:
    return sorted(
        (item for item in notifications if item.kind == "suspension"),
        key=lambda item: (item.tenant_id, item.sent_at),
    )


def suspend_overdue(repository: DunningRepository, as_of: date) -> SuspensionResult:
    threshold = as_of - timedelta(days=SUSPENSION_GRACE_DAYS)
    candidates = sorted(
        {
            invoice.tenant_id
            for invoice in repository.list_invoices()
            if invoice.status == "overdue" and utc_date(invoice.issued_at) <= threshold
        }
    )
    active = {tenant.tenant_id for tenant in repository.list_tenants() if tenant.status == "active"}
    sent_at = datetime.combine(as_of, time(), tzinfo=UTC)
    notifications = repository.list_notifications()
    suspended_tenants = []
    suspended_subscriptions = []
    created_notifications = []
    for tenant_id in candidates:
        if tenant_id not in active:
            continue
        repository.update_tenant_status(tenant_id, "suspended")
        suspended_tenants.append(tenant_id)
        for subscription in repository.list_subscriptions(tenant_id):
            if subscription.status != "active":
                continue
            if subscription.starts_on > as_of:
                raise SuspensionConflictError(
                    f"subscription {subscription.subscription_id} starts after {as_of.isoformat()}"
                )
            repository.suspend_subscription(subscription.subscription_id, as_of)
            suspended_subscriptions.append(
                SubscriptionRow(
                    subscription_id=subscription.subscription_id,
                    tenant_id=subscription.tenant_id,
                    plan_id=subscription.plan_id,
                    starts_on=subscription.starts_on,
                    ends_on=subscription.ends_on,
                    status="suspended",
                    suspended_on=as_of,
                )
            )
        already_sent = any(
            item.tenant_id == tenant_id and item.kind == "suspension" and item.sent_at == sent_at
            for item in notifications
        )
        if not already_sent:
            notification = NotificationRow(
                notification_id=md5_uuid(f"{tenant_id}suspension{as_of.isoformat()}"),
                tenant_id=tenant_id,
                kind="suspension",
                sent_at=sent_at,
            )
            repository.insert_notification(notification)
            notifications.append(notification)
            created_notifications.append(notification)
    return SuspensionResult(suspended_tenants, suspended_subscriptions, created_notifications)
