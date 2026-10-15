"""Dunning domain (services/legacy-billing/db/procs/dunning.sql): fn_overdue_accounts,
sp_schedule_dunning and sp_suspend_overdue over the invoices, tenants and subscriptions
documents the plans and invoicing units own, writing only notifications itself."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.domain import DunningAttemptRow, InvoiceRow, SubscriptionRow, legacy_uuid

SUSPENSION_GRACE_DAYS = 14
SUSPENSION = "suspension"


@dataclass(frozen=True)
class OverdueAccountRow:
    tenant_id: UUID
    invoice_id: UUID
    total: Decimal
    days_overdue: int
    tenant_status: str


@dataclass(frozen=True)
class NotificationRow:
    notification_id: UUID
    tenant_id: UUID
    kind: str
    sent_at: datetime


@dataclass(frozen=True)
class ScheduledInvoice:
    invoice: InvoiceRow
    attempt: DunningAttemptRow
    appended: bool


@dataclass(frozen=True)
class SuspensionRow:
    tenant_id: UUID
    tenant_status: str
    suspended_now: bool
    subscriptions: tuple[SubscriptionRow, ...]
    notifications: tuple[NotificationRow, ...]


class DunningRepository(Protocol):
    def list_overdue_invoices(self) -> list[InvoiceRow]: ...

    def tenant_status(self, tenant_id: UUID) -> str | None: ...

    def append_dunning_attempt(self, invoice_id: UUID, attempt: DunningAttemptRow) -> bool: ...

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...

    def suspend_tenant(self, tenant_id: UUID, as_of: date) -> list[SubscriptionRow]: ...

    def list_notifications(
        self, kind: str, tenant_id: UUID | None = None
    ) -> list[NotificationRow]: ...

    def insert_notification(self, notification: NotificationRow) -> bool: ...


def issued_on(invoice: InvoiceRow) -> date:
    """issued_at::date with the legacy session timezone UTC."""
    return invoice.issued_at.astimezone(UTC).date()


def _in_procedure_order(invoices: list[InvoiceRow]) -> list[InvoiceRow]:
    # ORDER BY issued_at, id (uuid order is bytewise, like UUID.int)
    return sorted(invoices, key=lambda invoice: (invoice.issued_at, invoice.invoice_id.int))


def overdue_accounts(repository: DunningRepository, as_of: date) -> list[OverdueAccountRow]:
    """fn_overdue_accounts: every overdue invoice issued before as_of joined to its tenant,
    days_overdue = as_of - issued date, in (issued_at, id) order."""
    rows = []
    for invoice in _in_procedure_order(repository.list_overdue_invoices()):
        issued = issued_on(invoice)
        if issued >= as_of:
            continue
        status = repository.tenant_status(invoice.tenant_id)
        if status is None:  # inner join to tenants
            continue
        rows.append(
            OverdueAccountRow(
                tenant_id=invoice.tenant_id,
                invoice_id=invoice.invoice_id,
                total=invoice.total,
                days_overdue=(as_of - issued).days,
                tenant_status=status,
            )
        )
    return rows


def next_business_day(day: date) -> date:
    """sp_schedule_dunning: a Saturday moves to Monday (+2), a Sunday to Monday (+1)."""
    if day.isoweekday() == 6:
        return day + timedelta(days=2)
    if day.isoweekday() == 7:
        return day + timedelta(days=1)
    return day


def schedule_dunning(repository: DunningRepository, as_of: date) -> list[ScheduledInvoice]:
    """sp_schedule_dunning: for every overdue invoice in (issued_at, id) order, append attempt
    max(attempt_no) + 1 scheduled for the next business day on or after as_of, id
    md5(invoice_id || attempt_no), status 'scheduled'. The append is idempotent on
    (invoiceId, attemptNo) through the invoicing owner API (ON CONFLICT DO NOTHING)."""
    scheduled_for = next_business_day(as_of)
    results = []
    for invoice in _in_procedure_order(repository.list_overdue_invoices()):
        attempt_no = max((item.attempt_no for item in invoice.dunning_attempts), default=0) + 1
        attempt = DunningAttemptRow(
            attempt_id=legacy_uuid(invoice.invoice_id, attempt_no),
            tenant_id=invoice.tenant_id,
            attempt_no=attempt_no,
            scheduled_for=scheduled_for,
            status="scheduled",
        )
        appended = repository.append_dunning_attempt(invoice.invoice_id, attempt)
        results.append(ScheduledInvoice(invoice, attempt, appended))
    return results


def suspension_notification(tenant_id: UUID, as_of: date) -> NotificationRow:
    # md5(tenant_id::text || 'suspension' || p_as_of::text)::uuid, sent_at = p_as_of::timestamptz
    return NotificationRow(
        notification_id=legacy_uuid(tenant_id, SUSPENSION, as_of.isoformat()),
        tenant_id=tenant_id,
        kind=SUSPENSION,
        sent_at=datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC),
    )


def suspend_overdue(repository: DunningRepository, as_of: date) -> list[SuspensionRow]:
    """sp_suspend_overdue: each distinct tenant with an overdue invoice issued on or before
    as_of - 14 days that is still active is suspended (tenant + active subscriptions, through
    the plans owner API) and gets one 'suspension' notification for as_of unless that
    (tenant, kind, sent_at) already exists. Tenants already suspended are left untouched, so
    a second run on the same day changes nothing."""
    if as_of.toordinal() <= SUSPENSION_GRACE_DAYS:
        return []  # no representable invoice date is 14 days old yet
    cutoff = as_of - timedelta(days=SUSPENSION_GRACE_DAYS)
    tenant_ids = sorted(
        {
            invoice.tenant_id
            for invoice in repository.list_overdue_invoices()
            if issued_on(invoice) <= cutoff
        },
        key=lambda tenant_id: tenant_id.int,
    )
    rows = []
    for tenant_id in tenant_ids:
        status = repository.tenant_status(tenant_id)
        if status is None:
            continue
        suspended_now = status == "active"
        if suspended_now:
            subscriptions = repository.suspend_tenant(tenant_id, as_of)
            repository.insert_notification(suspension_notification(tenant_id, as_of))
            status = "suspended"
        else:
            subscriptions = repository.list_subscriptions(tenant_id)
        rows.append(
            SuspensionRow(
                tenant_id=tenant_id,
                tenant_status=status,
                suspended_now=suspended_now,
                subscriptions=tuple(
                    sorted(subscriptions, key=lambda item: item.subscription_id.int)
                ),
                notifications=tuple(repository.list_notifications(SUSPENSION, tenant_id)),
            )
        )
    return rows
