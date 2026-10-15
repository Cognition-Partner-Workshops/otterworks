from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from test_rating import FEB_END, FEB_START, STARTER, SUBSCRIPTION, TENANT, FakeRatingRepository

from app.domain import (
    CreditNoteRow,
    DunningAttemptRow,
    InvoiceLineRow,
    InvoiceRow,
    NoSubscriptionError,
    SubscriptionRow,
    draw_down_credit,
    invoice_lines,
    invoice_preview,
    issue_invoice,
    legacy_uuid,
)

# used=201 on STARTER (100 included, 0.055/unit) is the 5.555 -> 5.56 overage of RATING-003
OVERAGE_USED = 201
PERIOD = legacy_uuid(TENANT, "2026-02-01")
INVOICE = legacy_uuid(PERIOD, "invoice")


def note(suffix: int, issued_on: date, amount: str, remaining: str | None = None) -> CreditNoteRow:
    return CreditNoteRow(
        UUID(f"70000000-0000-0000-0000-00000000000{suffix}"),
        issued_on,
        Decimal(amount),
        Decimal(remaining or amount),
    )


class FakeInvoicingRepository(FakeRatingRepository):
    def __init__(self, *, credit_notes: list[CreditNoteRow] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tax_exempt = False
        self.credit_notes = credit_notes or []
        self.invoices: dict[UUID, InvoiceRow] = {}
        self.credit_applied: list[Decimal] = []

    def tenant_tax_exempt(self, tenant_id: UUID) -> bool:
        return self.tax_exempt

    def list_credit_notes(self, tenant_id: UUID) -> list[CreditNoteRow]:
        return sorted(self.credit_notes, key=lambda item: (item.issued_on, item.note_id))

    def apply_credit(self, tenant_id: UUID, credit: Decimal) -> list[CreditNoteRow]:
        self.credit_applied.append(credit)
        self.credit_notes = draw_down_credit(self.credit_notes, credit)
        return self.list_credit_notes(tenant_id)

    def find_invoice(self, invoice_id: UUID) -> InvoiceRow | None:
        return self.invoices.get(invoice_id)

    def upsert_invoice(
        self,
        invoice_id: UUID,
        tenant_id: UUID,
        period_id: UUID,
        issued_at: date,
        subtotal: Decimal,
        tax: Decimal,
        total: Decimal,
        lines: list[InvoiceLineRow],
    ) -> InvoiceRow:
        existing = self.invoices.get(invoice_id)
        if existing is None:
            existing = InvoiceRow(
                invoice_id,
                tenant_id,
                period_id,
                datetime(issued_at.year, issued_at.month, issued_at.day, tzinfo=UTC),
                Decimal(0),
                Decimal(0),
                Decimal(0),
                "draft",
                (),
                (),
            )
        self.invoices[invoice_id] = replace(
            existing, status="issued", subtotal=subtotal, tax=tax, total=total, lines=tuple(lines)
        )
        return self.invoices[invoice_id]


@pytest.mark.rule("INVOICING-001")
def test_preview_lines_are_fee_overage_and_two_unrounded_tax_halves() -> None:
    lines = invoice_preview(FakeInvoicingRepository(used=OVERAGE_USED), TENANT, FEB_START, FEB_END)
    assert [line.line_no for line in lines] == [1, 2, 3, 4, 5]
    assert [line.line_type for line in lines] == ["plan", "usage", "tax", "tax", "credit"]
    assert [line.description for line in lines[:2]] == ["STARTER", "usage overage"]
    # (49 + 5.56) * 0.0825 = 4.5012, split in half and not rounded by the function
    assert [line.amount for line in lines] == [
        Decimal("49.00"),
        Decimal("5.56"),
        Decimal("2.250600"),
        Decimal("2.250600"),
        Decimal("0"),
    ]
    assert [line.total for line in lines[:4]] == [line.amount for line in lines[:4]]
    assert all(line.tax_amount == 0 for line in lines)


@pytest.mark.rule("INVOICING-001")
def test_preview_tax_is_zero_for_a_tax_exempt_tenant() -> None:
    repository = FakeInvoicingRepository(used=OVERAGE_USED)
    repository.tax_exempt = True
    lines = invoice_preview(repository, TENANT, FEB_START, FEB_END)
    assert [line.amount for line in lines[2:4]] == [Decimal("0"), Decimal("0")]


def test_preview_requires_a_subscription_covering_the_period() -> None:
    ended = SubscriptionRow(
        SUBSCRIPTION, TENANT, STARTER, date(2025, 1, 1), date(2025, 12, 31), "active", None
    )
    with pytest.raises(NoSubscriptionError):
        invoice_preview(FakeInvoicingRepository(subscription=ended), TENANT, FEB_START, FEB_END)


@pytest.mark.rule("INVOICING-002")
@pytest.mark.parametrize(
    ("notes", "applied"),
    [
        ([note(5, date(2026, 1, 31), "5.00"), note(6, date(2026, 2, 1), "55.00")], "53.04"),
        ([note(4, date(2026, 2, 2), "25.00")], "25.00"),
        ([note(4, date(2026, 2, 2), "25.00", "0.00")], "0"),
        ([], "0"),
    ],
)
def test_credit_line_applies_open_credit_up_to_the_rounded_charge(
    notes: list[CreditNoteRow], applied: str
) -> None:
    # 49 + 0 overage + 4.0425 tax rounds to a 53.04 charge
    repository = FakeInvoicingRepository(credit_notes=notes)
    credit = invoice_preview(repository, TENANT, FEB_START, FEB_END)[4]
    assert (credit.line_type, credit.description, credit.amount) == ("credit", "credit notes", 0)
    assert (credit.credit_applied, credit.total) == (Decimal(applied), -Decimal(applied))
    assert str(credit.total) != "-0"  # PostgreSQL numeric has no negative zero


@pytest.mark.rule("INVOICING-003")
def test_issue_invoice_uses_legacy_ids_rounds_each_line_and_finalizes_the_rating() -> None:
    repository = FakeInvoicingRepository(used=OVERAGE_USED)
    invoice, notes = issue_invoice(repository, TENANT, FEB_START, FEB_END)
    assert (invoice.invoice_id, invoice.period_id, invoice.tenant_id) == (INVOICE, PERIOD, TENANT)
    assert invoice.issued_at == datetime(2026, 2, 28, tzinfo=UTC)
    assert (invoice.status, invoice.subtotal, invoice.tax, invoice.total) == (
        "issued",
        Decimal("54.56"),
        Decimal("4.50"),
        Decimal("59.06"),
    )
    assert [(line.line_no, line.amount) for line in invoice.lines] == [
        (1, Decimal("49.00")),
        (2, Decimal("5.56")),
        (3, Decimal("2.25")),
        (4, Decimal("2.25")),
        (5, Decimal("0.00")),
    ]
    assert [line.line_id for line in invoice.lines] == [
        legacy_uuid(INVOICE, n) for n in range(1, 6)
    ]
    assert (TENANT, FEB_START) in repository.periods and notes == []
    assert repository.credit_applied == [Decimal("0")]


@pytest.mark.rule("INVOICING-003")
def test_issue_invoice_stores_the_negative_credit_total_and_nets_it_from_the_total() -> None:
    notes = [note(5, date(2026, 1, 31), "5.00"), note(6, date(2026, 2, 1), "55.00")]
    repository = FakeInvoicingRepository(credit_notes=notes)
    invoice, _ = issue_invoice(repository, TENANT, FEB_START, FEB_END)
    assert (invoice.subtotal, invoice.tax, invoice.total) == (
        Decimal("49.00"),
        Decimal("4.04"),
        Decimal("0.00"),
    )
    assert invoice.lines[4].amount == Decimal("-53.04")
    assert repository.credit_applied == [Decimal("53.04")]


@pytest.mark.rule("INVOICING-003")
def test_reissuing_keeps_the_invoice_row_and_replaces_its_lines() -> None:
    repository = FakeInvoicingRepository(used=OVERAGE_USED)
    attempt = DunningAttemptRow(UUID(int=8), TENANT, 1, date(2026, 3, 16), "sent")
    first, _ = issue_invoice(repository, TENANT, FEB_START, FEB_END)
    repository.invoices[INVOICE] = replace(
        first, status="overdue", dunning_attempts=(attempt,), lines=first.lines[:1]
    )
    repository.used = 0
    second, _ = issue_invoice(repository, TENANT, FEB_START, FEB_END)
    assert (second.invoice_id, second.issued_at, second.status) == (
        INVOICE,
        first.issued_at,
        "issued",
    )
    assert second.dunning_attempts == (attempt,)
    assert len(second.lines) == 5 and (second.subtotal, second.total) == (
        Decimal("49.00"),
        Decimal("53.04"),
    )
    assert len(repository.invoices) == 1


@pytest.mark.rule("INVOICING-004")
def test_credit_is_drawn_down_oldest_note_first_then_by_id() -> None:
    # tenant 9 of the seed: 5.00 issued 2026-01-31, 55.00 issued 2026-02-01, 53.04 applied
    drawn = draw_down_credit(
        [note(6, date(2026, 2, 1), "55.00"), note(5, date(2026, 1, 31), "5.00")], Decimal("53.04")
    )
    assert [(n.note_id.int & 0xF, n.remaining_amount) for n in drawn] == [
        (5, Decimal("0.00")),
        (6, Decimal("6.96")),
    ]
    # tenant 4: equal dates order by id, so ...0001 is consumed before ...0002
    drawn = draw_down_credit(
        [note(2, date(2026, 2, 1), "30.00"), note(1, date(2026, 2, 1), "30.00")], Decimal("53.04")
    )
    assert [(n.note_id.int & 0xF, n.remaining_amount) for n in drawn] == [
        (1, Decimal("0.00")),
        (2, Decimal("6.96")),
    ]


@pytest.mark.rule("INVOICING-004")
def test_drawdown_skips_exhausted_notes_and_stops_once_the_credit_is_consumed() -> None:
    notes = [
        note(1, date(2026, 1, 1), "10.00", "0.00"),
        note(2, date(2026, 1, 2), "10.00"),
        note(3, date(2026, 1, 3), "10.00"),
    ]
    drawn = draw_down_credit(notes, Decimal("4.00"))
    assert [n.remaining_amount for n in drawn] == [
        Decimal("0.00"),
        Decimal("6.00"),
        Decimal("10.00"),
    ]
    assert draw_down_credit(notes, Decimal("0")) == notes


@pytest.mark.rule("INVOICING-005")
def test_invoice_lines_are_returned_in_line_order_and_empty_for_an_unknown_invoice() -> None:
    repository = FakeInvoicingRepository()
    second = InvoiceLineRow(UUID(int=2), 2, "usage", "usage overage", Decimal("12.29"))
    first = InvoiceLineRow(UUID(int=1), 1, "plan", "GROWTH", Decimal("149.00"))
    repository.invoices[INVOICE] = InvoiceRow(
        INVOICE,
        TENANT,
        PERIOD,
        datetime(2026, 2, 1, tzinfo=UTC),
        Decimal("149.00"),
        Decimal("12.29"),
        Decimal("161.29"),
        "overdue",
        (second, first),
        (),
    )
    assert invoice_lines(repository, INVOICE) == [first, second]
    assert invoice_lines(repository, UUID(int=99)) == []
