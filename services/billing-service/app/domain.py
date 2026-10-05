from __future__ import annotations

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


TAX_RATE = Decimal("0.0825")
CENT = Decimal("0.01")
ZERO = Decimal("0")


@dataclass(frozen=True)
class InvoiceLine:
    line_no: int
    line_type: str
    description: str
    amount: Decimal
    tax_amount: Decimal
    credit_applied: Decimal
    total: Decimal


@dataclass(frozen=True)
class StoredInvoiceLine:
    line_no: int
    line_type: str
    description: str
    amount: Decimal


@dataclass(frozen=True)
class CreditNoteRow:
    credit_id: UUID
    issued_on: date
    amount: Decimal
    remaining_amount: Decimal


@dataclass(frozen=True)
class InvoiceTotals:
    subtotal: Decimal
    tax: Decimal
    credit_applied: Decimal
    total: Decimal


def round_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def md5_uuid(value: str) -> UUID:
    return UUID(hashlib.md5(value.encode()).hexdigest())


def rating_period_id(tenant_id: UUID, period_start: date) -> UUID:
    return md5_uuid(f"{tenant_id}{period_start.isoformat()}")


def invoice_id_for(period_id: UUID) -> UUID:
    return md5_uuid(f"{period_id}invoice")


def invoice_line_id(invoice_id: UUID, line_no: int) -> UUID:
    return md5_uuid(f"{invoice_id}{line_no}")


def available_credit(notes: list[CreditNoteRow]) -> Decimal:
    return sum((note.remaining_amount for note in notes if note.remaining_amount > 0), ZERO)


def preview_lines(
    plan: PlanRow,
    overage_amount: Decimal,
    tax_exempt: bool | None,
    credit_balance: Decimal,
) -> list[InvoiceLine]:
    tax = ZERO if tax_exempt else (plan.monthly_fee + overage_amount) * TAX_RATE
    half_tax = tax / 2
    credit = min(credit_balance, round_money(plan.monthly_fee + overage_amount + tax))
    fee = round_money(plan.monthly_fee)
    usage = round_money(overage_amount)
    return [
        InvoiceLine(1, "plan", plan.code, fee, ZERO, ZERO, fee),
        InvoiceLine(2, "usage", "usage overage", usage, ZERO, ZERO, usage),
        InvoiceLine(3, "tax", "regional tax", half_tax, ZERO, ZERO, half_tax),
        InvoiceLine(4, "tax", "local tax", half_tax, ZERO, ZERO, half_tax),
        InvoiceLine(5, "credit", "credit notes", ZERO, ZERO, credit, ZERO - credit),
    ]


def persisted_lines(lines: list[InvoiceLine]) -> list[StoredInvoiceLine]:
    return [
        StoredInvoiceLine(
            line.line_no,
            line.line_type,
            line.description,
            round_money(line.total if line.line_type == "credit" else line.amount),
        )
        for line in lines
    ]


def invoice_totals(lines: list[InvoiceLine]) -> InvoiceTotals:
    subtotal = ZERO
    tax = ZERO
    credit = ZERO
    for line in lines:
        if line.line_type in ("plan", "usage"):
            subtotal += round_money(line.amount)
        elif line.line_type == "tax":
            tax += round_money(line.amount)
        elif line.line_type == "credit":
            credit = line.credit_applied
    return InvoiceTotals(
        subtotal=round_money(subtotal),
        tax=round_money(tax),
        credit_applied=credit,
        total=round_money(subtotal + tax - credit),
    )


def consume_credits(
    notes: list[CreditNoteRow], credit_applied: Decimal
) -> list[tuple[UUID, Decimal]]:
    outstanding = credit_applied
    updates: list[tuple[UUID, Decimal]] = []
    open_notes = sorted(
        (note for note in notes if note.remaining_amount > 0),
        key=lambda note: (note.issued_on, note.credit_id),
    )
    for note in open_notes:
        if outstanding <= 0:
            break
        updates.append((note.credit_id, max(note.remaining_amount - outstanding, ZERO)))
        outstanding = max(outstanding - note.remaining_amount, ZERO)
    return updates
