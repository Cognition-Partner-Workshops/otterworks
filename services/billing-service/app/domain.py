from __future__ import annotations

import calendar
import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
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
            next_status = subscription.status if subscription.status == "cancelled" else "active"
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


FIRST_TIER_UNITS = 101
SECOND_TIER_MULTIPLIER = Decimal("1.5")
ROLLOVER_WINDOW_MONTHS = 3
ROLLOVER_CAP_MULTIPLIER = 2
CENT = Decimal("0.01")


@dataclass(frozen=True)
class UsageEventRow:
    tenant_id: UUID
    occurred_at: datetime
    units: int
    kind: str


@dataclass(frozen=True)
class RatingHistoryRow:
    period_start: date
    rollover_units: int


@dataclass(frozen=True)
class UsageRating:
    tenant_id: UUID
    period_start: date
    period_end: date
    subscription_id: UUID
    used_units: int
    quota_units: int
    rollover_units: int
    billable_units: int
    first_tier_units: int
    second_tier_units: int
    overage_amount: Decimal


@dataclass(frozen=True)
class UsageSummaryRow:
    kind: str
    event_count: int
    units: int


@dataclass(frozen=True)
class RatingPeriodRow:
    period_id: UUID
    tenant_id: UUID
    period_start: date
    period_end: date


@dataclass(frozen=True)
class RatingResultRow:
    result_id: UUID
    period_id: UUID
    subscription_id: UUID
    used_units: int
    quota_units: int
    rollover_units: int
    billable_units: int
    overage_amount: Decimal
    created_at: datetime


class NoSubscriptionError(LookupError):
    pass


class RatingRepository(Protocol):
    def list_plans(self) -> list[PlanRow]: ...

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...

    def list_usage_events(self, tenant_id: UUID) -> list[UsageEventRow]: ...

    def list_rating_history(self, tenant_id: UUID) -> list[RatingHistoryRow]: ...

    def find_rating_period(self, tenant_id: UUID, period_start: date) -> RatingPeriodRow | None: ...

    def insert_rating_period(self, period: RatingPeriodRow) -> None: ...

    def update_rating_period_end(self, period_id: UUID, period_end: date) -> None: ...

    def find_rating_result(self, result_id: UUID) -> RatingResultRow | None: ...

    def insert_rating_result(self, result: RatingResultRow) -> None: ...

    def update_rating_result(self, result: RatingResultRow) -> None: ...

    def list_rating_results(self, tenant_id: UUID, period_start: date) -> list[RatingResultRow]: ...


def round_half_up(value: Decimal, exponent: Decimal) -> Decimal:
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def _base10000(value: int) -> tuple[int, int]:
    digits = []
    while value:
        value, digit = divmod(value, 10000)
        digits.append(digit)
    return len(digits) - 1, digits[-1]


def pg_numeric_quotient(numerator: int, denominator: int) -> Decimal:
    """Divide two positive integers with PostgreSQL's numeric result scale (select_div_scale)."""
    weight1, first1 = _base10000(numerator)
    weight2, first2 = _base10000(denominator)
    quotient_weight = weight1 - weight2 - (1 if first1 <= first2 else 0)
    scale = min(max(16 - quotient_weight * 4, 0), 1000)
    with localcontext() as context:
        context.prec = scale + 40
        return round_half_up(Decimal(numerator) / Decimal(denominator), Decimal(1).scaleb(-scale))


def months_before(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def legacy_md5_uuid(text: str) -> UUID:
    return UUID(hashlib.md5(text.encode(), usedforsecurity=False).hexdigest())


def select_subscription(
    subscriptions: list[SubscriptionRow], period_start: date, period_end: date
) -> SubscriptionRow | None:
    overlapping = [
        item
        for item in subscriptions
        if item.starts_on <= period_end and (item.ends_on is None or item.ends_on >= period_start)
    ]
    return max(overlapping, key=lambda item: item.starts_on, default=None)


def _in_period(event: UsageEventRow, period_start: date, period_end: date) -> bool:
    return period_start <= event.occurred_at.astimezone(UTC).date() <= period_end


def used_units(events: list[UsageEventRow], period_start: date, period_end: date) -> int:
    return sum(event.units for event in events if _in_period(event, period_start, period_end))


def rollover_units(history: list[RatingHistoryRow], period_start: date, included_units: int) -> int:
    window_start = months_before(period_start, ROLLOVER_WINDOW_MONTHS)
    prior = sum(
        row.rollover_units for row in history if window_start <= row.period_start < period_start
    )
    cap = ROLLOVER_CAP_MULTIPLIER * included_units
    return min(min(cap, prior), cap)


def billable_units(used: int, rollover: int, included_units: int) -> int:
    return max(used - rollover - included_units, 0)


def tier_split(billable: int) -> tuple[int, int]:
    return min(billable, FIRST_TIER_UNITS), max(billable - FIRST_TIER_UNITS, 0)


def overage_amount(first_tier: int, second_tier: int, overage_rate: Decimal) -> Decimal:
    exact = first_tier * overage_rate + second_tier * overage_rate * SECOND_TIER_MULTIPLIER
    return round_half_up(exact, CENT)


def suspension_factor(
    subscription: SubscriptionRow, period_start: date, period_end: date
) -> Decimal | None:
    if (
        subscription.status != "suspended"
        or subscription.suspended_on is None
        or not period_start <= subscription.suspended_on <= period_end
    ):
        return None
    suspended_days = (period_end - subscription.suspended_on).days + 1
    period_days = (period_end - period_start).days + 1
    return pg_numeric_quotient(suspended_days, period_days)


def prorate(billable: int, amount: Decimal, factor: Decimal) -> tuple[int, Decimal]:
    with localcontext() as context:
        context.prec = 80
        return (
            int(round_half_up(billable * factor, Decimal(1))),
            round_half_up(amount * factor, CENT),
        )


def rate_usage(
    repository: RatingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> UsageRating:
    subscription = select_subscription(
        repository.list_subscriptions(tenant_id), period_start, period_end
    )
    if subscription is None:
        raise NoSubscriptionError(tenant_id)
    plan = next(item for item in repository.list_plans() if item.plan_id == subscription.plan_id)
    used = used_units(repository.list_usage_events(tenant_id), period_start, period_end)
    rollover = rollover_units(
        repository.list_rating_history(tenant_id), period_start, plan.included_units
    )
    billable = billable_units(used, rollover, plan.included_units)
    first_tier, second_tier = tier_split(billable)
    amount = overage_amount(first_tier, second_tier, plan.overage_rate)
    factor = suspension_factor(subscription, period_start, period_end)
    if factor is not None:
        billable, amount = prorate(billable, amount, factor)
    return UsageRating(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        subscription_id=subscription.subscription_id,
        used_units=used,
        quota_units=plan.included_units,
        rollover_units=rollover,
        billable_units=billable,
        first_tier_units=first_tier,
        second_tier_units=second_tier,
        overage_amount=amount,
    )


def usage_summary(
    events: list[UsageEventRow], period_start: date, period_end: date
) -> list[UsageSummaryRow]:
    totals: dict[str, tuple[int, int]] = {}
    for event in events:
        if _in_period(event, period_start, period_end):
            count, units = totals.get(event.kind, (0, 0))
            totals[event.kind] = (count + 1, units + event.units)
    return [
        UsageSummaryRow(kind=kind, event_count=count, units=units)
        for kind, (count, units) in sorted(totals.items())
    ]


def rating_period_id(tenant_id: UUID, period_start: date) -> UUID:
    return legacy_md5_uuid(f"{tenant_id}{period_start.isoformat()}")


def rating_result_id(period_id: UUID) -> UUID:
    return legacy_md5_uuid(str(period_id))


def finalize_rating(
    repository: RatingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> list[RatingResultRow]:
    rating = rate_usage(repository, tenant_id, period_start, period_end)
    period_id = rating_period_id(tenant_id, period_start)
    existing_period = repository.find_rating_period(tenant_id, period_start)
    if existing_period is None:
        repository.insert_rating_period(
            RatingPeriodRow(period_id, tenant_id, period_start, period_end)
        )
    else:
        repository.update_rating_period_end(existing_period.period_id, period_end)
    result = RatingResultRow(
        result_id=rating_result_id(period_id),
        period_id=period_id,
        subscription_id=rating.subscription_id,
        used_units=rating.used_units,
        quota_units=rating.quota_units,
        rollover_units=max(rating.quota_units - rating.used_units, 0),
        billable_units=rating.billable_units,
        overage_amount=rating.overage_amount,
        created_at=datetime.combine(period_end, time.min, tzinfo=UTC),
    )
    if repository.find_rating_result(result.result_id) is None:
        repository.insert_rating_result(result)
    else:
        repository.update_rating_result(result)
    return repository.list_rating_results(tenant_id, period_start)


TAX_RATE = Decimal("0.0825")


@dataclass(frozen=True)
class CreditNoteRow:
    credit_id: UUID
    tenant_id: UUID
    issued_on: date
    amount: Decimal
    remaining_amount: Decimal


@dataclass(frozen=True)
class InvoicePreviewLine:
    line_no: int
    line_type: str
    description: str
    amount: Decimal
    tax_amount: Decimal
    credit_applied: Decimal
    total: Decimal


@dataclass(frozen=True)
class InvoiceRow:
    invoice_id: UUID
    tenant_id: UUID
    period_id: UUID
    issued_at: datetime
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    status: str


@dataclass(frozen=True)
class InvoiceLineRow:
    line_id: UUID
    invoice_id: UUID
    line_no: int
    line_type: str
    description: str
    amount: Decimal


@dataclass(frozen=True)
class InvoiceTotals:
    subtotal: Decimal
    tax: Decimal
    credit: Decimal
    total: Decimal


@dataclass(frozen=True)
class IssuedInvoice:
    invoice: InvoiceRow
    period_invoices: list[InvoiceRow]
    credit_notes: list[CreditNoteRow]


class NegativeInvoiceTotalError(ValueError):
    pass


class InvoicingRepository(RatingRepository, Protocol):
    def find_tax_exempt(self, tenant_id: UUID) -> bool | None: ...

    def list_credit_notes(self, tenant_id: UUID) -> list[CreditNoteRow]: ...

    def lock_credit_notes(self, tenant_id: UUID) -> list[CreditNoteRow]: ...

    def update_credit_remaining(self, credit_id: UUID, remaining_amount: Decimal) -> None: ...

    def find_invoice(self, invoice_id: UUID) -> InvoiceRow | None: ...

    def insert_invoice(self, invoice: InvoiceRow) -> None: ...

    def update_invoice_status(self, invoice_id: UUID, status: str) -> None: ...

    def update_invoice_totals(self, invoice_id: UUID, totals: InvoiceTotals) -> None: ...

    def list_period_invoices(self, period_id: UUID) -> list[InvoiceRow]: ...

    def delete_invoice_lines(self, invoice_id: UUID) -> None: ...

    def insert_invoice_line(self, line: InvoiceLineRow) -> None: ...

    def list_invoice_lines(self, invoice_id: UUID) -> list[InvoiceLineRow]: ...


def invoice_tax(monthly_fee: Decimal, overage: Decimal, tax_exempt: bool | None) -> Decimal:
    return Decimal(0) if tax_exempt else (monthly_fee + overage) * TAX_RATE


def available_credit(notes: list[CreditNoteRow]) -> Decimal:
    return sum((note.remaining_amount for note in notes if note.remaining_amount > 0), Decimal(0))


def credit_applied(
    credit: Decimal, monthly_fee: Decimal, overage: Decimal, tax: Decimal
) -> Decimal:
    return min(credit, round_half_up(monthly_fee + overage + tax, CENT))


def preview_lines(
    plan_code: str,
    monthly_fee: Decimal,
    overage: Decimal,
    tax_exempt: bool | None,
    credit: Decimal,
) -> list[InvoicePreviewLine]:
    tax = invoice_tax(monthly_fee, overage, tax_exempt)
    tax_half = tax / 2
    applied = credit_applied(credit, monthly_fee, overage, tax)
    zero = Decimal(0)
    plan_amount = round_half_up(monthly_fee, CENT)
    usage_amount = round_half_up(overage, CENT)
    return [
        InvoicePreviewLine(1, "plan", plan_code, plan_amount, zero, zero, plan_amount),
        InvoicePreviewLine(2, "usage", "usage overage", usage_amount, zero, zero, usage_amount),
        InvoicePreviewLine(3, "tax", "regional tax", tax_half, zero, zero, tax_half),
        InvoicePreviewLine(4, "tax", "local tax", tax_half, zero, zero, tax_half),
        InvoicePreviewLine(5, "credit", "credit notes", zero, zero, applied, zero - applied),
    ]


def invoice_preview(
    repository: InvoicingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> list[InvoicePreviewLine]:
    rating = rate_usage(repository, tenant_id, period_start, period_end)
    subscription = next(
        item
        for item in repository.list_subscriptions(tenant_id)
        if item.subscription_id == rating.subscription_id
    )
    plan = next(item for item in repository.list_plans() if item.plan_id == subscription.plan_id)
    return preview_lines(
        plan.code,
        plan.monthly_fee,
        rating.overage_amount,
        repository.find_tax_exempt(tenant_id),
        available_credit(repository.list_credit_notes(tenant_id)),
    )


def invoice_id_for(period_id: UUID) -> UUID:
    return legacy_md5_uuid(f"{period_id}invoice")


def invoice_line_id(invoice_id: UUID, line_no: int) -> UUID:
    return legacy_md5_uuid(f"{invoice_id}{line_no}")


def stored_lines(invoice_id: UUID, lines: list[InvoicePreviewLine]) -> list[InvoiceLineRow]:
    return [
        InvoiceLineRow(
            line_id=invoice_line_id(invoice_id, line.line_no),
            invoice_id=invoice_id,
            line_no=line.line_no,
            line_type=line.line_type,
            description=line.description,
            amount=round_half_up(line.total if line.line_type == "credit" else line.amount, CENT),
        )
        for line in lines
    ]


def invoice_totals(lines: list[InvoicePreviewLine]) -> InvoiceTotals:
    subtotal = Decimal(0)
    tax = Decimal(0)
    credit = Decimal(0)
    for line in lines:
        if line.line_type in ("plan", "usage"):
            subtotal += round_half_up(line.amount, CENT)
        elif line.line_type == "tax":
            tax += round_half_up(line.amount, CENT)
        elif line.line_type == "credit":
            credit = line.credit_applied
    return InvoiceTotals(subtotal, tax, credit, round_half_up(subtotal + tax - credit, CENT))


def consume_credit(notes: list[CreditNoteRow], credit: Decimal) -> list[tuple[UUID, Decimal]]:
    updates = []
    remaining = credit
    for note in sorted(notes, key=lambda item: (item.issued_on, item.credit_id)):
        if remaining <= 0:
            break
        if note.remaining_amount <= 0:
            continue
        used = min(note.remaining_amount, remaining)
        updates.append((note.credit_id, note.remaining_amount - used))
        remaining -= used
    return updates


def issue_invoice(
    repository: InvoicingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> IssuedInvoice:
    repository.lock_credit_notes(tenant_id)
    lines = invoice_preview(repository, tenant_id, period_start, period_end)
    totals = invoice_totals(lines)
    if totals.total < 0:
        raise NegativeInvoiceTotalError(totals.total)
    finalize_rating(repository, tenant_id, period_start, period_end)
    period_id = rating_period_id(tenant_id, period_start)
    invoice_id = invoice_id_for(period_id)
    if repository.find_invoice(invoice_id) is None:
        repository.insert_invoice(
            InvoiceRow(
                invoice_id=invoice_id,
                tenant_id=tenant_id,
                period_id=period_id,
                issued_at=datetime.combine(period_end, time.min, tzinfo=UTC),
                subtotal=Decimal(0),
                tax=Decimal(0),
                total=Decimal(0),
                status="issued",
            )
        )
    else:
        repository.update_invoice_status(invoice_id, "issued")
    repository.delete_invoice_lines(invoice_id)
    for line in stored_lines(invoice_id, lines):
        repository.insert_invoice_line(line)
    repository.update_invoice_totals(invoice_id, totals)
    for credit_id, remaining_amount in consume_credit(
        repository.list_credit_notes(tenant_id), totals.credit
    ):
        repository.update_credit_remaining(credit_id, remaining_amount)
    invoice = repository.find_invoice(invoice_id)
    assert invoice is not None
    return IssuedInvoice(
        invoice=invoice,
        period_invoices=repository.list_period_invoices(period_id),
        credit_notes=sorted(
            repository.list_credit_notes(tenant_id),
            key=lambda item: (item.issued_on, item.credit_id),
        ),
    )


def invoice_lines(rows: list[InvoiceLineRow]) -> list[InvoiceLineRow]:
    return sorted(rows, key=lambda item: item.line_no)
