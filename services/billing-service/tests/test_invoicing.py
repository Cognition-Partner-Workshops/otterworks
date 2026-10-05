from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.domain import (
    CreditNoteRow,
    InvoiceTotals,
    PlanRow,
    StoredInvoiceLine,
    SubscriptionRow,
    invoice_id_for,
    invoice_line_id,
    invoice_totals,
    preview_lines,
    rating_period_id,
)
from app.invoicing import issue_invoice, preview_invoice
from app.invoicing_rating import UsageRating

TENANT = UUID("00000000-0000-0000-0000-000000000006")
STARTER = PlanRow(
    UUID("10000000-0000-0000-0000-000000000001"),
    "STARTER",
    "starter",
    Decimal("49.00"),
    100,
    Decimal("0.055000"),
    True,
)
GROWTH = PlanRow(
    UUID("10000000-0000-0000-0000-000000000002"),
    "GROWTH",
    "growth",
    Decimal("149.00"),
    1000,
    Decimal("0.040000"),
    True,
)
START = date(2026, 2, 1)
END = date(2026, 2, 28)


def subscription(plan: PlanRow, starts_on: date, ends_on: date | None = None) -> SubscriptionRow:
    return SubscriptionRow(
        UUID(int=starts_on.toordinal()), TENANT, plan.plan_id, starts_on, ends_on, "active", None
    )


def credit(suffix: int, issued_on: date, remaining: str) -> CreditNoteRow:
    return CreditNoteRow(
        UUID(f"70000000-0000-0000-0000-{suffix:012d}"),
        issued_on,
        Decimal(remaining),
        Decimal(remaining),
    )


class FakeRepository:
    def __init__(
        self,
        subscriptions: list[SubscriptionRow],
        used: int = 0,
        tax_exempt: bool | None = False,
        credits: list[CreditNoteRow] | None = None,
    ) -> None:
        self.subscriptions = subscriptions
        self.plans = {STARTER.plan_id: STARTER, GROWTH.plan_id: GROWTH}
        self.used = used
        self.tax_exempt = tax_exempt
        self.credits = {note.credit_id: note for note in credits or []}
        self.periods: dict[UUID, tuple[date, date]] = {}
        self.results: dict[UUID, tuple[UUID, UsageRating, int]] = {}
        self.invoices: dict[UUID, dict] = {}
        self.lines: dict[UUID, list[StoredInvoiceLine]] = {}

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        return list(self.subscriptions)

    def get_plan(self, plan_id: UUID) -> PlanRow:
        return self.plans[plan_id]

    def tenant_tax_exempt(self, tenant_id: UUID) -> bool | None:
        return self.tax_exempt

    def used_units(self, tenant_id: UUID, period_start: date, period_end: date) -> int:
        return self.used

    def rollover_history(self, tenant_id: UUID) -> list[tuple[date, int]]:
        return []

    def list_credit_notes(self, tenant_id: UUID) -> list[CreditNoteRow]:
        return sorted(self.credits.values(), key=lambda note: (note.issued_on, note.credit_id))

    def upsert_rating_period(
        self, period_id: UUID, tenant_id: UUID, period_start: date, period_end: date
    ) -> None:
        self.periods[period_id] = (period_start, period_end)

    def upsert_rating_result(
        self,
        result_id: UUID,
        period_id: UUID,
        subscription_id: UUID,
        rating: UsageRating,
        rollover_units: int,
        created_on: date,
    ) -> None:
        self.results[result_id] = (period_id, rating, rollover_units)

    def upsert_invoice(
        self, invoice_id: UUID, tenant_id: UUID, period_id: UUID, issued_on: date
    ) -> None:
        existing = self.invoices.get(invoice_id)
        if existing is None:
            self.invoices[invoice_id] = {
                "period_id": period_id,
                "issued_on": issued_on,
                "status": "issued",
            }
        else:
            existing["status"] = "issued"

    def replace_invoice_lines(self, invoice_id: UUID, lines: list[StoredInvoiceLine]) -> None:
        self.lines[invoice_id] = list(lines)

    def update_invoice_totals(self, invoice_id: UUID, totals: InvoiceTotals) -> None:
        self.invoices[invoice_id]["totals"] = totals

    def update_credit_remaining(self, credit_id: UUID, remaining_amount: Decimal) -> None:
        note = self.credits[credit_id]
        self.credits[credit_id] = CreditNoteRow(
            note.credit_id, note.issued_on, note.amount, remaining_amount
        )


@pytest.mark.rule("INVOICE-001")
def test_preview_has_five_lines_from_latest_overlapping_subscription() -> None:
    repository = FakeRepository(
        [
            subscription(GROWTH, date(2025, 1, 1), date(2026, 2, 1)),
            subscription(STARTER, date(2026, 1, 1)),
            subscription(GROWTH, date(2026, 3, 1)),
        ]
    )
    lines = preview_invoice(repository, TENANT, START, END)
    assert [(line.line_no, line.line_type, line.description) for line in lines] == [
        (1, "plan", "STARTER"),
        (2, "usage", "usage overage"),
        (3, "tax", "regional tax"),
        (4, "tax", "local tax"),
        (5, "credit", "credit notes"),
    ]
    assert lines[0].amount == Decimal("49.00")


@pytest.mark.rule("INVOICE-001")
def test_subscription_ending_on_period_start_still_overlaps() -> None:
    repository = FakeRepository([subscription(GROWTH, date(2025, 1, 1), START)])
    assert preview_invoice(repository, TENANT, START, END)[0].description == "GROWTH"


@pytest.mark.rule("INVOICE-002")
def test_usage_line_uses_rated_overage() -> None:
    repository = FakeRepository([subscription(STARTER, date(2026, 1, 1))], used=201)
    usage = preview_invoice(repository, TENANT, START, END)[1]
    assert usage.amount == Decimal("5.56")
    assert usage.total == Decimal("5.56")


@pytest.mark.rule("INVOICE-003")
def test_tax_halves_are_unrounded_and_tax_amount_is_zero() -> None:
    lines = preview_lines(STARTER, Decimal("5.56"), False, Decimal("0"))
    assert lines[2].amount == lines[3].amount == Decimal("2.2506")
    assert lines[2].total == Decimal("2.2506")
    assert all(line.tax_amount == 0 for line in lines)


@pytest.mark.rule("INVOICE-003")
def test_tax_exempt_tenant_has_zero_tax() -> None:
    lines = preview_lines(STARTER, Decimal("5.02"), True, Decimal("25.00"))
    assert lines[2].amount == lines[3].amount == 0


@pytest.mark.rule("INVOICE-004")
def test_credit_is_capped_at_rounded_gross_after_tax() -> None:
    credit_line = preview_lines(STARTER, Decimal("0"), False, Decimal("60.00"))[4]
    assert credit_line.credit_applied == Decimal("53.04")
    assert credit_line.total == Decimal("-53.04")
    assert credit_line.amount == 0


@pytest.mark.rule("INVOICE-004")
def test_zero_credit_line_is_not_negative_zero() -> None:
    credit_line = preview_lines(STARTER, Decimal("0"), False, Decimal("0"))[4]
    assert str(credit_line.total) == "0"


@pytest.mark.rule("INVOICE-005")
def test_issue_finalizes_rating_and_upserts_invoice_with_deterministic_ids() -> None:
    repository = FakeRepository([subscription(STARTER, date(2026, 1, 1))], used=201)
    issued = issue_invoice(repository, TENANT, START, END)
    period_id = rating_period_id(TENANT, START)
    assert issued.period_id == period_id
    assert issued.invoice_id == invoice_id_for(period_id)
    assert repository.periods[period_id] == (START, END)
    assert len(repository.results) == 1
    assert repository.invoices[issued.invoice_id]["issued_on"] == END
    repository.invoices[issued.invoice_id]["status"] = "paid"
    issue_invoice(repository, TENANT, START, END)
    assert repository.invoices[issued.invoice_id]["status"] == "issued"


@pytest.mark.rule("INVOICE-006")
def test_issue_replaces_lines_with_rounded_amounts() -> None:
    repository = FakeRepository(
        [subscription(STARTER, date(2026, 1, 1))],
        credits=[credit(1, date(2026, 2, 1), "60.00")],
    )
    issued = issue_invoice(repository, TENANT, START, END)
    stored = repository.lines[issued.invoice_id]
    assert [(line.line_type, line.amount) for line in stored] == [
        ("plan", Decimal("49.00")),
        ("usage", Decimal("0.00")),
        ("tax", Decimal("2.02")),
        ("tax", Decimal("2.02")),
        ("credit", Decimal("-53.04")),
    ]
    assert invoice_line_id(issued.invoice_id, 1) != invoice_line_id(issued.invoice_id, 2)


@pytest.mark.rule("INVOICE-007")
def test_totals_round_each_tax_half_then_subtract_credit() -> None:
    totals = invoice_totals(preview_lines(STARTER, Decimal("5.56"), False, Decimal("0")))
    assert totals == InvoiceTotals(
        Decimal("54.56"), Decimal("4.50"), Decimal("0"), Decimal("59.06")
    )
    capped = invoice_totals(preview_lines(STARTER, Decimal("0"), False, Decimal("60.00")))
    assert (capped.subtotal, capped.tax, capped.total) == (
        Decimal("49.00"),
        Decimal("4.04"),
        Decimal("0.00"),
    )


@pytest.mark.rule("INVOICE-008")
def test_credit_is_consumed_oldest_first_then_by_id() -> None:
    repository = FakeRepository(
        [subscription(STARTER, date(2026, 1, 1))],
        credits=[
            credit(2, date(2026, 2, 1), "30.00"),
            credit(1, date(2026, 2, 1), "30.00"),
        ],
    )
    issue_invoice(repository, TENANT, START, END)
    remaining = [
        (str(note.credit_id)[-1], note.remaining_amount)
        for note in repository.list_credit_notes(TENANT)
    ]
    assert remaining == [("1", Decimal("0.00")), ("2", Decimal("6.96"))]


@pytest.mark.rule("INVOICE-009")
def test_invoice_lines_endpoint_returns_lines_in_order(monkeypatch) -> None:
    invoice_id = UUID("60000000-0000-0000-0000-000000000001")

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class FakeLinesRepository:
        def __init__(self, _connection: object) -> None:
            pass

        def list_invoice_lines(self, requested: UUID) -> list[StoredInvoiceLine]:
            assert requested == invoice_id
            return [
                StoredInvoiceLine(1, "plan", "GROWTH", Decimal("149.00")),
                StoredInvoiceLine(2, "usage", "usage overage", Decimal("12.29")),
            ]

    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "PostgresInvoicingRepository", FakeLinesRepository)
    response = TestClient(main.app).get(f"/api/invoices/{invoice_id}/lines")
    assert response.status_code == 200
    assert response.json() == [
        {"line_no": 1, "line_type": "plan", "description": "GROWTH", "amount": "149.00"},
        {"line_no": 2, "line_type": "usage", "description": "usage overage", "amount": "12.29"},
    ]
