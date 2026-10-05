from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.domain import (
    CreditNoteRow,
    InvoiceLine,
    InvoiceTotals,
    PlanRow,
    StoredInvoiceLine,
    SubscriptionRow,
    available_credit,
    consume_credits,
    invoice_id_for,
    invoice_totals,
    md5_uuid,
    persisted_lines,
    preview_lines,
    rating_period_id,
)
from app.invoicing_rating import (
    UsageRating,
    finalized_rollover,
    prior_rollover,
    rate_usage,
    select_subscription,
)


class InvoicingRepository(Protocol):
    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]: ...

    def get_plan(self, plan_id: UUID) -> PlanRow: ...

    def tenant_tax_exempt(self, tenant_id: UUID) -> bool | None: ...

    def used_units(self, tenant_id: UUID, period_start: date, period_end: date) -> int: ...

    def rollover_history(self, tenant_id: UUID) -> list[tuple[date, int]]: ...

    def list_credit_notes(self, tenant_id: UUID) -> list[CreditNoteRow]: ...

    def upsert_rating_period(
        self, period_id: UUID, tenant_id: UUID, period_start: date, period_end: date
    ) -> None: ...

    def upsert_rating_result(
        self,
        result_id: UUID,
        period_id: UUID,
        subscription_id: UUID,
        rating: UsageRating,
        rollover_units: int,
        created_on: date,
    ) -> None: ...

    def upsert_invoice(
        self, invoice_id: UUID, tenant_id: UUID, period_id: UUID, issued_on: date
    ) -> None: ...

    def replace_invoice_lines(self, invoice_id: UUID, lines: list[StoredInvoiceLine]) -> None: ...

    def update_invoice_totals(self, invoice_id: UUID, totals: InvoiceTotals) -> None: ...

    def update_credit_remaining(self, credit_id: UUID, remaining_amount: Decimal) -> None: ...


@dataclass(frozen=True)
class IssuedInvoice:
    invoice_id: UUID
    period_id: UUID
    totals: InvoiceTotals


class NoSubscriptionError(LookupError):
    pass


def _rate(
    repository: InvoicingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> tuple[SubscriptionRow, PlanRow, UsageRating]:
    # Temporary copy of billing.fn_usage_rating pending the rating extraction.
    subscription = select_subscription(
        repository.list_subscriptions(tenant_id), period_start, period_end
    )
    if subscription is None:
        raise NoSubscriptionError(str(tenant_id))
    plan = repository.get_plan(subscription.plan_id)
    rating = rate_usage(
        plan,
        subscription,
        repository.used_units(tenant_id, period_start, period_end),
        prior_rollover(plan, repository.rollover_history(tenant_id), period_start),
        period_start,
        period_end,
    )
    return subscription, plan, rating


def finalize_rating(
    repository: InvoicingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> UUID:
    # Temporary copy of billing.sp_finalize_rating pending the rating extraction.
    period_id = rating_period_id(tenant_id, period_start)
    repository.upsert_rating_period(period_id, tenant_id, period_start, period_end)
    subscription, _plan, rating = _rate(repository, tenant_id, period_start, period_end)
    repository.upsert_rating_result(
        md5_uuid(str(period_id)),
        period_id,
        subscription.subscription_id,
        rating,
        finalized_rollover(rating),
        period_end,
    )
    return period_id


def preview_invoice(
    repository: InvoicingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> list[InvoiceLine]:
    _subscription, plan, rating = _rate(repository, tenant_id, period_start, period_end)
    return preview_lines(
        plan,
        rating.overage_amount,
        repository.tenant_tax_exempt(tenant_id),
        available_credit(repository.list_credit_notes(tenant_id)),
    )


def issue_invoice(
    repository: InvoicingRepository, tenant_id: UUID, period_start: date, period_end: date
) -> IssuedInvoice:
    period_id = finalize_rating(repository, tenant_id, period_start, period_end)
    invoice_id = invoice_id_for(period_id)
    repository.upsert_invoice(invoice_id, tenant_id, period_id, period_end)
    lines = preview_invoice(repository, tenant_id, period_start, period_end)
    repository.replace_invoice_lines(invoice_id, persisted_lines(lines))
    totals = invoice_totals(lines)
    repository.update_invoice_totals(invoice_id, totals)
    for credit_id, remaining in consume_credits(
        repository.list_credit_notes(tenant_id), totals.credit_applied
    ):
        repository.update_credit_remaining(credit_id, remaining)
    return IssuedInvoice(invoice_id=invoice_id, period_id=period_id, totals=totals)
