from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app import main
from app.domain import (
    InvoiceLineRow,
    InvoiceTotals,
    InvoicingCreditNote,
    InvoicingError,
    InvoicingOverage,
    InvoicingPlan,
    InvoicingPriorRollover,
    InvoicingSubscription,
    build_invoice_preview,
    consume_credit_notes,
    invoice_preview,
    invoice_totals,
    invoicing_invoice_id,
    invoicing_period_id,
    invoicing_subscription,
    issue_invoice,
)

TENANT = UUID("00000000-0000-0000-0000-000000000006")
SUBSCRIPTION = UUID("20000000-0000-0000-0000-000000000006")
START = date(2026, 2, 1)
END = date(2026, 2, 28)
STARTER = InvoicingPlan("STARTER", Decimal("49.00"), 100, Decimal("0.0550"))
GROWTH = InvoicingPlan("GROWTH", Decimal("149.00"), 500, Decimal("0.0400"))


def subscription(
    plan: InvoicingPlan = STARTER,
    starts_on: date = date(2026, 1, 1),
    ends_on: date | None = None,
    status: str = "active",
    suspended_on: date | None = None,
    subscription_id: UUID = SUBSCRIPTION,
) -> InvoicingSubscription:
    return InvoicingSubscription(subscription_id, starts_on, ends_on, status, suspended_on, plan)


def note(suffix: int, issued_on: date, remaining: str) -> InvoicingCreditNote:
    return InvoicingCreditNote(
        UUID(f"70000000-0000-0000-0000-{suffix:012d}"), issued_on, Decimal(remaining)
    )


class FakeInvoicingRepository:
    def __init__(
        self,
        subscriptions: list[InvoicingSubscription] | None = None,
        used_units: int = 0,
        tax_exempt: bool | None = False,
        credit_notes: list[InvoicingCreditNote] | None = None,
        prior_rollovers: list[InvoicingPriorRollover] | None = None,
    ) -> None:
        self.subscriptions = subscriptions if subscriptions is not None else [subscription()]
        self.used_units = used_units
        self.tax_exempt = tax_exempt
        self.credit_notes = list(credit_notes or [])
        self.prior_rollovers = list(prior_rollovers or [])
        self.calls: list[str] = []
        self.rating_periods: dict[UUID, tuple[UUID, date, date]] = {}
        self.rating_results: dict[UUID, tuple] = {}
        self.invoices: dict[UUID, dict] = {}
        self.lines: dict[UUID, list[tuple[UUID, InvoiceLineRow]]] = {}

    def list_invoicing_subscriptions(self, tenant_id: UUID) -> list[InvoicingSubscription]:
        return list(self.subscriptions)

    def tenant_tax_exempt(self, tenant_id: UUID) -> bool | None:
        return self.tax_exempt

    def sum_usage_units(self, tenant_id: UUID, period_start: date, period_end: date) -> int:
        return self.used_units

    def list_prior_rollovers(self, tenant_id: UUID) -> list[InvoicingPriorRollover]:
        return list(self.prior_rollovers)

    def list_open_credit_notes(self, tenant_id: UUID) -> list[InvoicingCreditNote]:
        return [item for item in self.credit_notes if item.remaining_amount > 0]

    def upsert_rating_period(
        self, period_id: UUID, tenant_id: UUID, period_start: date, period_end: date
    ) -> None:
        self.calls.append("rating_period")
        self.rating_periods[period_id] = (tenant_id, period_start, period_end)

    def upsert_rating_result(
        self,
        result_id: UUID,
        period_id: UUID,
        subscription_id: UUID,
        overage: InvoicingOverage,
        rollover_units: int,
        created_on: date,
    ) -> None:
        self.calls.append("rating_result")
        self.rating_results[result_id] = (period_id, subscription_id, overage, rollover_units)

    def upsert_issued_invoice(
        self, invoice_id: UUID, tenant_id: UUID, period_id: UUID, issued_on: date
    ) -> None:
        self.calls.append("invoice")
        invoice = self.invoices.setdefault(
            invoice_id,
            {"period_id": period_id, "issued_on": issued_on, "totals": None},
        )
        invoice["status"] = "issued"

    def replace_invoice_lines(
        self, invoice_id: UUID, lines: list[tuple[UUID, InvoiceLineRow]]
    ) -> None:
        self.lines[invoice_id] = list(lines)

    def update_invoice_totals(self, invoice_id: UUID, totals: InvoiceTotals) -> None:
        self.invoices[invoice_id]["totals"] = totals

    def update_credit_note_remaining(self, credit_note_id: UUID, remaining: Decimal) -> None:
        self.credit_notes = [
            replace(item, remaining_amount=remaining)
            if item.credit_note_id == credit_note_id
            else item
            for item in self.credit_notes
        ]

    def list_invoice_lines(self, invoice_id: UUID) -> list[InvoiceLineRow]:
        return sorted((line for _, line in self.lines.get(invoice_id, [])), key=lambda x: x.line_no)


def amounts(lines) -> list[Decimal | None]:
    return [line.amount for line in lines]


@pytest.mark.rule("INVOICE-001")
def test_preview_has_five_fixed_lines_even_when_zero() -> None:
    lines = invoice_preview(FakeInvoicingRepository(used_units=10), TENANT, START, END)

    assert [line.line_no for line in lines] == [1, 2, 3, 4, 5]
    assert [line.line_type for line in lines] == ["plan", "usage", "tax", "tax", "credit"]
    assert [line.description for line in lines] == [
        "STARTER",
        "usage overage",
        "regional tax",
        "local tax",
        "credit notes",
    ]
    assert all(line.tax_amount == 0 for line in lines)
    assert lines[1].amount == Decimal("0.00")
    assert lines[4].total == Decimal("0")


@pytest.mark.rule("INVOICE-002")
def test_plan_line_charges_latest_overlapping_plan_in_full() -> None:
    subscriptions = [
        subscription(STARTER, date(2026, 1, 1), date(2026, 2, 14)),
        subscription(GROWTH, date(2026, 2, 15), subscription_id=UUID(int=2)),
        subscription(GROWTH, date(2026, 3, 1), subscription_id=UUID(int=3)),
    ]
    chosen = invoicing_subscription(subscriptions, START, END)
    assert chosen is not None and chosen.plan == GROWTH
    assert invoicing_subscription([subscription(ends_on=START)], START, END) is not None
    assert invoicing_subscription([subscription(starts_on=END)], START, END) is not None

    suspended = subscription(GROWTH, status="suspended", suspended_on=date(2026, 2, 15))
    lines = invoice_preview(FakeInvoicingRepository([suspended]), TENANT, START, END)
    assert lines[0].amount == lines[0].total == Decimal("149.00")

    missing = invoice_preview(
        FakeInvoicingRepository([], credit_notes=[note(1, START, "5.00")]), TENANT, START, END
    )
    assert amounts(missing)[:4] == [None, None, None, None]
    assert missing[0].description is None
    assert missing[4].credit_applied == Decimal("5.00")


@pytest.mark.rule("INVOICE-003")
def test_usage_line_uses_invoicing_local_overage() -> None:
    lines = invoice_preview(FakeInvoicingRepository(used_units=201), TENANT, START, END)
    assert lines[1].amount == lines[1].total == Decimal("5.56")

    tiered = invoice_preview(FakeInvoicingRepository(used_units=302), TENANT, START, END)
    assert tiered[1].amount == Decimal("13.89")

    rollover = FakeInvoicingRepository(
        used_units=201,
        prior_rollovers=[
            InvoicingPriorRollover(date(2025, 11, 1), 150),
            InvoicingPriorRollover(date(2025, 10, 1), 999),
            InvoicingPriorRollover(START, 999),
        ],
    )
    assert invoice_preview(rollover, TENANT, START, END)[1].amount == Decimal("0.00")

    suspended = FakeInvoicingRepository(
        [subscription(status="suspended", suspended_on=date(2026, 2, 15))], used_units=201
    )
    assert invoice_preview(suspended, TENANT, START, END)[1].amount == Decimal("2.78")


@pytest.mark.rule("INVOICE-004")
def test_tax_is_split_unrounded_and_skipped_for_exempt_tenants() -> None:
    lines = build_invoice_preview(STARTER, Decimal("5.56"), False, Decimal(0))
    assert lines[2].amount == lines[3].amount == Decimal("2.250600")

    exempt = build_invoice_preview(STARTER, Decimal("5.56"), True, Decimal(0))
    assert exempt[2].amount == exempt[3].amount == Decimal(0)

    unknown_tenant = build_invoice_preview(STARTER, Decimal("5.56"), None, Decimal(0))
    assert unknown_tenant[2].amount == Decimal("2.250600")


@pytest.mark.rule("INVOICE-005")
def test_credit_line_caps_total_remaining_credit_at_gross() -> None:
    repository = FakeInvoicingRepository(
        credit_notes=[note(5, date(2026, 1, 31), "5.00"), note(6, date(2026, 3, 1), "55.00")]
    )
    credit = invoice_preview(repository, TENANT, START, END)[4]
    assert credit.amount == Decimal(0)
    assert credit.credit_applied == Decimal("53.04")
    assert credit.total == Decimal("-53.04")

    small = build_invoice_preview(STARTER, Decimal(0), False, Decimal("10.00"))[4]
    assert small.credit_applied == Decimal("10.00")


@pytest.mark.rule("INVOICE-006")
def test_issue_upserts_deterministic_invoice_and_replaces_lines() -> None:
    repository = FakeInvoicingRepository(used_units=201)
    invoice_id, period_id = issue_invoice(repository, TENANT, START, END)

    assert period_id == invoicing_period_id(TENANT, START)
    assert invoice_id == invoicing_invoice_id(period_id)
    assert repository.invoices[invoice_id]["status"] == "issued"
    assert repository.invoices[invoice_id]["issued_on"] == END
    stored = repository.list_invoice_lines(invoice_id)
    assert [line.amount for line in stored] == [
        Decimal("49.00"),
        Decimal("5.56"),
        Decimal("2.25"),
        Decimal("2.25"),
        Decimal("0.00"),
    ]

    repository.invoices[invoice_id]["status"] = "paid"
    issue_invoice(repository, TENANT, START, END)
    assert repository.invoices[invoice_id]["status"] == "issued"
    assert len(repository.list_invoice_lines(invoice_id)) == 5


@pytest.mark.rule("INVOICE-006")
def test_reissue_reapplies_remaining_credit() -> None:
    repository = FakeInvoicingRepository(
        credit_notes=[note(5, date(2026, 1, 31), "5.00"), note(6, START, "55.00")]
    )
    invoice_id, _ = issue_invoice(repository, TENANT, START, END)
    assert repository.invoices[invoice_id]["totals"].total == Decimal("0.00")

    issue_invoice(repository, TENANT, START, END)
    assert repository.invoices[invoice_id]["totals"].total == Decimal("46.08")
    assert [item.remaining_amount for item in repository.credit_notes] == [
        Decimal("0"),
        Decimal("0"),
    ]


@pytest.mark.rule("INVOICE-007")
def test_issue_finalizes_rating_before_writing_invoice() -> None:
    repository = FakeInvoicingRepository(used_units=201)
    invoice_id, period_id = issue_invoice(repository, TENANT, START, END)

    assert repository.calls[:3] == ["rating_period", "rating_result", "invoice"]
    assert repository.rating_periods[period_id] == (TENANT, START, END)
    (result,) = repository.rating_results.values()
    assert result[0] == period_id and result[1] == SUBSCRIPTION
    assert result[2].billable_units == 101 and result[2].overage_amount == Decimal("5.56")
    assert result[3] == 0

    with pytest.raises(InvoicingError):
        issue_invoice(FakeInvoicingRepository([]), TENANT, START, END)


@pytest.mark.rule("INVOICE-008")
def test_totals_round_each_tax_half_and_subtract_unrounded_cap() -> None:
    preview = build_invoice_preview(STARTER, Decimal("5.56"), False, Decimal(0))
    assert invoice_totals(preview) == InvoiceTotals(
        Decimal("54.56"), Decimal("4.50"), Decimal("59.06"), Decimal(0)
    )

    capped = build_invoice_preview(STARTER, Decimal(0), False, Decimal("60.00"))
    assert invoice_totals(capped).total == Decimal("0.00")

    odd_fee = replace(STARTER, monthly_fee=Decimal("49.07"))
    mismatch = build_invoice_preview(odd_fee, Decimal(0), False, Decimal("60.00"))
    assert invoice_totals(mismatch).total == Decimal("-0.01")
    repository = FakeInvoicingRepository(
        [subscription(odd_fee)], credit_notes=[note(1, START, "60.00")]
    )
    with pytest.raises(InvoicingError):
        issue_invoice(repository, TENANT, START, END)


@pytest.mark.rule("INVOICE-009")
def test_credit_is_consumed_oldest_first_with_uuid_tie_break() -> None:
    notes = [note(2, START, "30.00"), note(1, START, "30.00"), note(9, date(2026, 1, 1), "5.00")]
    updates = consume_credit_notes(notes, Decimal("53.04"))
    assert updates == [
        (notes[2].credit_note_id, Decimal("0")),
        (notes[1].credit_note_id, Decimal("0")),
        (notes[0].credit_note_id, Decimal("11.96")),
    ]
    assert consume_credit_notes(notes, Decimal(0)) == []


@pytest.mark.rule("INVOICE-010")
def test_invoice_lines_endpoint_returns_rows_in_line_order(monkeypatch) -> None:
    rows = [
        InvoiceLineRow(1, "plan", "GROWTH", Decimal("149.00")),
        InvoiceLineRow(2, "usage", "usage overage", Decimal("12.29")),
    ]

    class FakeRepository:
        def __init__(self, connection) -> None:
            pass

        def list_invoice_lines(self, invoice_id: UUID) -> list[InvoiceLineRow]:
            return rows if invoice_id == UUID(int=1) else []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

    monkeypatch.setattr(main, "PostgresInvoicingRepository", FakeRepository)
    monkeypatch.setattr(main, "connect", FakeConnection)
    monkeypatch.setattr(main, "migrate", lambda: None)
    with TestClient(main.app) as client:
        response = client.get(f"/api/invoices/{UUID(int=1)}/lines")
        missing = client.get(f"/api/invoices/{UUID(int=2)}/lines")

    assert response.status_code == 200
    assert response.json() == [
        {"line_no": 1, "line_type": "plan", "description": "GROWTH", "amount": "149.00"},
        {"line_no": 2, "line_type": "usage", "description": "usage overage", "amount": "12.29"},
    ]
    assert missing.json() == []
