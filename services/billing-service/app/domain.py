from __future__ import annotations

import calendar
import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
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


# --- invoicing ----------------------------------------------------------------
# Extracted from services/legacy-billing/db/procs/invoicing.sql (INVOICE-001..010).

INVOICE_TAX_RATE = Decimal("0.0825")
INVOICE_FIRST_TIER_UNITS = 101
INVOICE_SECOND_TIER_MULTIPLIER = Decimal("1.5")
INVOICE_ROLLOVER_LOOKBACK_MONTHS = 3
_CENTS = Decimal("0.01")


class InvoicingError(Exception):
    pass


@dataclass(frozen=True)
class InvoicingPlan:
    code: str
    monthly_fee: Decimal
    included_units: int
    overage_rate: Decimal


@dataclass(frozen=True)
class InvoicingSubscription:
    subscription_id: UUID
    starts_on: date
    ends_on: date | None
    status: str
    suspended_on: date | None
    plan: InvoicingPlan


@dataclass(frozen=True)
class InvoicingPriorRollover:
    period_start: date
    rollover_units: int


@dataclass(frozen=True)
class InvoicingOverage:
    used_units: int
    quota_units: int
    rollover_units: int
    billable_units: int
    overage_amount: Decimal


@dataclass(frozen=True)
class InvoicingCreditNote:
    credit_note_id: UUID
    issued_on: date
    remaining_amount: Decimal


@dataclass(frozen=True)
class InvoicePreviewLine:
    line_no: int
    line_type: str
    description: str | None
    amount: Decimal | None
    tax_amount: Decimal
    credit_applied: Decimal | None
    total: Decimal | None


@dataclass(frozen=True)
class InvoiceLineRow:
    line_no: int
    line_type: str
    description: str
    amount: Decimal


@dataclass(frozen=True)
class InvoiceTotals:
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    credit_applied: Decimal


class InvoicingRepository(Protocol):
    def list_invoicing_subscriptions(self, tenant_id: UUID) -> list[InvoicingSubscription]: ...

    def tenant_tax_exempt(self, tenant_id: UUID) -> bool | None: ...

    def sum_usage_units(self, tenant_id: UUID, period_start: date, period_end: date) -> int: ...

    def list_prior_rollovers(self, tenant_id: UUID) -> list[InvoicingPriorRollover]: ...

    def list_open_credit_notes(self, tenant_id: UUID) -> list[InvoicingCreditNote]: ...

    def upsert_rating_period(
        self, period_id: UUID, tenant_id: UUID, period_start: date, period_end: date
    ) -> None: ...

    def upsert_rating_result(
        self,
        result_id: UUID,
        period_id: UUID,
        subscription_id: UUID,
        overage: InvoicingOverage,
        rollover_units: int,
        created_on: date,
    ) -> None: ...

    def upsert_issued_invoice(
        self, invoice_id: UUID, tenant_id: UUID, period_id: UUID, issued_on: date
    ) -> None: ...

    def replace_invoice_lines(
        self, invoice_id: UUID, lines: list[tuple[UUID, InvoiceLineRow]]
    ) -> None: ...

    def update_invoice_totals(self, invoice_id: UUID, totals: InvoiceTotals) -> None: ...

    def update_credit_note_remaining(self, credit_note_id: UUID, remaining: Decimal) -> None: ...

    def list_invoice_lines(self, invoice_id: UUID) -> list[InvoiceLineRow]: ...


def invoicing_round(value: Decimal) -> Decimal:
    """PostgreSQL round(numeric, 2): half away from zero."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _md5_uuid(text: str) -> UUID:
    return UUID(hashlib.md5(text.encode()).hexdigest())


def invoicing_period_id(tenant_id: UUID, period_start: date) -> UUID:
    return _md5_uuid(f"{tenant_id}{period_start.isoformat()}")


def invoicing_invoice_id(period_id: UUID) -> UUID:
    return _md5_uuid(f"{period_id}invoice")


def invoicing_line_id(invoice_id: UUID, line_no: int) -> UUID:
    return _md5_uuid(f"{invoice_id}{line_no}")


def invoicing_rating_result_id(period_id: UUID) -> UUID:
    return _md5_uuid(str(period_id))


def _months_before(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def invoicing_subscription(
    subscriptions: list[InvoicingSubscription], period_start: date, period_end: date
) -> InvoicingSubscription | None:
    overlapping = [
        item
        for item in subscriptions
        if item.starts_on <= period_end and (item.ends_on is None or item.ends_on >= period_start)
    ]
    return max(overlapping, key=lambda item: item.starts_on, default=None)


def _invoicing_usage_overage(
    subscription: InvoicingSubscription | None,
    used_units: int,
    prior_rollovers: list[InvoicingPriorRollover],
    period_start: date,
    period_end: date,
) -> InvoicingOverage | None:
    """Invoicing-private copy of the rating rules (billing.fn_usage_rating).

    Duplicates the rating module's overage calculation so invoicing is extracted
    independently; consolidate onto the shared rating domain function once it lands.
    """
    if subscription is None:
        return None
    plan = subscription.plan
    lookback = _months_before(period_start, INVOICE_ROLLOVER_LOOKBACK_MONTHS)
    prior = min(
        2 * plan.included_units,
        sum(
            item.rollover_units
            for item in prior_rollovers
            if lookback <= item.period_start < period_start
        ),
    )
    rollover = min(prior, plan.included_units * 2)
    billable = max(used_units - rollover - plan.included_units, 0)
    first = min(billable, INVOICE_FIRST_TIER_UNITS)
    second = max(billable - INVOICE_FIRST_TIER_UNITS, 0)
    amount = invoicing_round(
        first * plan.overage_rate + second * plan.overage_rate * INVOICE_SECOND_TIER_MULTIPLIER
    )
    if (
        subscription.status == "suspended"
        and subscription.suspended_on is not None
        and period_start <= subscription.suspended_on <= period_end
    ):
        factor = Decimal((period_end - subscription.suspended_on).days + 1) / Decimal(
            (period_end - period_start).days + 1
        )
        billable = int((billable * factor).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        amount = invoicing_round(amount * factor)
    return InvoicingOverage(used_units, plan.included_units, rollover, billable, amount)


def _invoicing_rate(
    repository: InvoicingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> tuple[InvoicingSubscription | None, InvoicingOverage | None]:
    subscription = invoicing_subscription(
        repository.list_invoicing_subscriptions(tenant_id), period_start, period_end
    )
    overage = _invoicing_usage_overage(
        subscription,
        repository.sum_usage_units(tenant_id, period_start, period_end),
        repository.list_prior_rollovers(tenant_id),
        period_start,
        period_end,
    )
    return subscription, overage


def invoice_tax(
    tax_exempt: bool | None, monthly_fee: Decimal | None, overage: Decimal | None
) -> Decimal | None:
    if tax_exempt:
        return Decimal(0)
    if monthly_fee is None or overage is None:
        return None
    return (monthly_fee + overage) * INVOICE_TAX_RATE


def build_invoice_preview(
    plan: InvoicingPlan | None,
    overage_amount: Decimal | None,
    tax_exempt: bool | None,
    open_credit: Decimal,
) -> list[InvoicePreviewLine]:
    fee = plan.monthly_fee if plan else None
    tax = invoice_tax(tax_exempt, fee, overage_amount)
    half_tax = tax / 2 if tax is not None else None
    gross = (
        invoicing_round(fee + overage_amount + tax)
        if fee is not None and overage_amount is not None and tax is not None
        else None
    )
    credit = open_credit if gross is None else min(open_credit, gross)
    zero = Decimal(0)
    rounded_fee = invoicing_round(fee) if fee is not None else None
    rounded_overage = invoicing_round(overage_amount) if overage_amount is not None else None
    return [
        InvoicePreviewLine(
            1, "plan", plan.code if plan else None, rounded_fee, zero, zero, rounded_fee
        ),
        InvoicePreviewLine(
            2, "usage", "usage overage", rounded_overage, zero, zero, rounded_overage
        ),
        InvoicePreviewLine(3, "tax", "regional tax", half_tax, zero, zero, half_tax),
        InvoicePreviewLine(4, "tax", "local tax", half_tax, zero, zero, half_tax),
        InvoicePreviewLine(5, "credit", "credit notes", zero, zero, credit, zero - credit),
    ]


def invoice_preview(
    repository: InvoicingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> list[InvoicePreviewLine]:
    subscription, overage = _invoicing_rate(repository, tenant_id, period_start, period_end)
    open_credit = sum(
        (item.remaining_amount for item in repository.list_open_credit_notes(tenant_id)),
        Decimal(0),
    )
    return build_invoice_preview(
        subscription.plan if subscription else None,
        overage.overage_amount if overage else None,
        repository.tenant_tax_exempt(tenant_id),
        open_credit,
    )


def persisted_invoice_lines(lines: list[InvoicePreviewLine]) -> list[InvoiceLineRow]:
    persisted = []
    for line in lines:
        amount = line.total if line.line_type == "credit" else line.amount
        if line.description is None or amount is None:
            raise InvoicingError("no subscription covers the invoice period")
        persisted.append(
            InvoiceLineRow(line.line_no, line.line_type, line.description, invoicing_round(amount))
        )
    return persisted


def invoice_totals(lines: list[InvoicePreviewLine]) -> InvoiceTotals:
    subtotal = Decimal(0)
    tax = Decimal(0)
    credit = Decimal(0)
    for line in lines:
        if line.line_type in {"plan", "usage"}:
            subtotal += invoicing_round(line.amount)
        elif line.line_type == "tax":
            tax += invoicing_round(line.amount)
        elif line.line_type == "credit":
            credit = line.credit_applied
    return InvoiceTotals(
        invoicing_round(subtotal),
        invoicing_round(tax),
        invoicing_round(subtotal + tax - credit),
        credit,
    )


def consume_credit_notes(
    notes: list[InvoicingCreditNote], credit: Decimal
) -> list[tuple[UUID, Decimal]]:
    updates = []
    for note in sorted(notes, key=lambda item: (item.issued_on, item.credit_note_id)):
        if credit <= 0:
            break
        updates.append((note.credit_note_id, max(note.remaining_amount - credit, Decimal(0))))
        credit = max(credit - note.remaining_amount, Decimal(0))
    return updates


def finalize_invoicing_rating(
    repository: InvoicingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> UUID:
    period_id = invoicing_period_id(tenant_id, period_start)
    repository.upsert_rating_period(period_id, tenant_id, period_start, period_end)
    subscription, overage = _invoicing_rate(repository, tenant_id, period_start, period_end)
    if subscription is None or overage is None:
        raise InvoicingError("no subscription covers the invoice period")
    repository.upsert_rating_result(
        invoicing_rating_result_id(period_id),
        period_id,
        subscription.subscription_id,
        overage,
        max(overage.quota_units - overage.used_units, 0),
        period_end,
    )
    return period_id


def issue_invoice(
    repository: InvoicingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> tuple[UUID, UUID]:
    period_id = finalize_invoicing_rating(repository, tenant_id, period_start, period_end)
    invoice_id = invoicing_invoice_id(period_id)
    repository.upsert_issued_invoice(invoice_id, tenant_id, period_id, period_end)
    preview = invoice_preview(repository, tenant_id, period_start, period_end)
    repository.replace_invoice_lines(
        invoice_id,
        [
            (invoicing_line_id(invoice_id, line.line_no), line)
            for line in persisted_invoice_lines(preview)
        ],
    )
    totals = invoice_totals(preview)
    if totals.total < 0:
        raise InvoicingError("invoice total would be negative")
    repository.update_invoice_totals(invoice_id, totals)
    for credit_note_id, remaining in consume_credit_notes(
        repository.list_open_credit_notes(tenant_id), totals.credit_applied
    ):
        repository.update_credit_note_remaining(credit_note_id, remaining)
    return invoice_id, period_id
