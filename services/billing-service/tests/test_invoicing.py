from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.domain import (
    CreditNoteRow,
    InvoiceLineRow,
    InvoicePreviewLine,
    InvoiceRow,
    InvoiceTotals,
    NegativeInvoiceTotalError,
    NoSubscriptionError,
    PlanRow,
    SubscriptionRow,
    UsageEventRow,
    available_credit,
    consume_credit,
    credit_applied,
    invoice_id_for,
    invoice_line_id,
    invoice_lines,
    invoice_preview,
    invoice_tax,
    invoice_totals,
    issue_invoice,
    legacy_md5_uuid,
    preview_lines,
    rating_period_id,
    rating_result_id,
    stored_lines,
)
from tests.test_rating import FakeRatingRepository

TENANT = UUID("00000000-0000-0000-0000-000000000009")
STARTER = UUID("10000000-0000-0000-0000-000000000001")
GROWTH = UUID("10000000-0000-0000-0000-000000000002")
SUB_OLD = UUID("20000000-0000-0000-0000-000000000001")
SUB_NEW = UUID("20000000-0000-0000-0000-000000000002")
NOTE_A = UUID("70000000-0000-0000-0000-000000000001")
NOTE_B = UUID("70000000-0000-0000-0000-000000000002")
NOTE_C = UUID("70000000-0000-0000-0000-000000000003")
FEB_START = date(2026, 2, 1)
FEB_END = date(2026, 2, 28)
ZERO = Decimal(0)


def plan(plan_id: UUID, code: str, fee: str, included: int = 100) -> PlanRow:
    return PlanRow(plan_id, code, code.lower(), Decimal(fee), included, Decimal("0.055000"), True)


def subscription(
    subscription_id: UUID = SUB_OLD,
    plan_id: UUID = STARTER,
    starts_on: date = date(2025, 1, 1),
    ends_on: date | None = None,
    status: str = "active",
    suspended_on: date | None = None,
) -> SubscriptionRow:
    return SubscriptionRow(
        subscription_id, TENANT, plan_id, starts_on, ends_on, status, suspended_on
    )


def note(credit_id: UUID, issued_on: date, remaining: str, amount: str = "100.00") -> CreditNoteRow:
    return CreditNoteRow(credit_id, TENANT, issued_on, Decimal(amount), Decimal(remaining))


class FakeInvoicingRepository(FakeRatingRepository):
    def __init__(
        self,
        subscriptions: list[SubscriptionRow],
        plans: list[PlanRow] | None = None,
        events: list[UsageEventRow] | None = None,
        tax_exempt: bool | None = False,
        notes: list[CreditNoteRow] | None = None,
    ) -> None:
        super().__init__(subscriptions, events)
        self.plans = plans or [plan(STARTER, "STARTER", "49.00")]
        self.tax_exempt = tax_exempt
        self.notes = {item.credit_id: item for item in notes or []}
        self.invoices: dict[UUID, InvoiceRow] = {}
        self.lines: dict[UUID, InvoiceLineRow] = {}
        self.writes: list[str] = []
        self.locked_before_reads: list[bool] = []
        self.priced = False

    def list_plans(self) -> list[PlanRow]:
        return self.plans

    def insert_rating_period(self, period) -> None:
        self.writes.append("rating_period")
        super().insert_rating_period(period)

    def find_tax_exempt(self, _tenant_id: UUID) -> bool | None:
        self.priced = True
        return self.tax_exempt

    def list_credit_notes(self, tenant_id: UUID) -> list[CreditNoteRow]:
        return [item for item in self.notes.values() if item.tenant_id == tenant_id]

    def lock_credit_notes(self, tenant_id: UUID) -> list[CreditNoteRow]:
        self.locked_before_reads.append(not self.priced)
        return self.list_credit_notes(tenant_id)

    def update_credit_remaining(self, credit_id: UUID, remaining_amount: Decimal) -> None:
        self.writes.append("credit")
        self.notes[credit_id] = replace(self.notes[credit_id], remaining_amount=remaining_amount)

    def find_invoice(self, invoice_id: UUID) -> InvoiceRow | None:
        return self.invoices.get(invoice_id)

    def insert_invoice(self, invoice: InvoiceRow) -> None:
        self.writes.append("invoice")
        self.invoices[invoice.invoice_id] = invoice

    def update_invoice_status(self, invoice_id: UUID, status: str) -> None:
        self.invoices[invoice_id] = replace(self.invoices[invoice_id], status=status)

    def update_invoice_totals(self, invoice_id: UUID, totals: InvoiceTotals) -> None:
        self.invoices[invoice_id] = replace(
            self.invoices[invoice_id],
            subtotal=totals.subtotal,
            tax=totals.tax,
            total=totals.total,
        )

    def list_period_invoices(self, period_id: UUID) -> list[InvoiceRow]:
        return [item for item in self.invoices.values() if item.period_id == period_id]

    def delete_invoice_lines(self, invoice_id: UUID) -> None:
        self.lines = {
            key: item for key, item in self.lines.items() if item.invoice_id != invoice_id
        }

    def insert_invoice_line(self, line: InvoiceLineRow) -> None:
        assert line.line_id not in self.lines
        self.lines[line.line_id] = line

    def list_invoice_lines(self, invoice_id: UUID) -> list[InvoiceLineRow]:
        return [item for item in self.lines.values() if item.invoice_id == invoice_id]


def usage(units: int, day: int = 10) -> UsageEventRow:
    return UsageEventRow(TENANT, datetime(2026, 2, day, 12, tzinfo=UTC), units, "api")


class FakeConnection:
    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "migrate", lambda: None)
    monkeypatch.setattr(main, "connect", FakeConnection)
    with TestClient(main.app) as test_client:
        yield test_client


ISSUE_BODY = {"period_start": "2026-02-01", "period_end": "2026-02-28"}
PREVIEW_QUERY = "period_start=2026-02-01&period_end=2026-02-28"


@pytest.mark.rule("INVOICING-R01")
def test_plan_line_uses_latest_overlapping_subscription_at_full_fee() -> None:
    older = subscription(SUB_OLD, STARTER, date(2025, 1, 1), date(2026, 2, 14), "cancelled")
    latest = subscription(
        SUB_NEW, GROWTH, date(2026, 2, 10), status="suspended", suspended_on=date(2026, 2, 15)
    )
    repository = FakeInvoicingRepository(
        [older, latest],
        plans=[plan(STARTER, "STARTER", "49.00"), plan(GROWTH, "GROWTH", "149.004", 500)],
    )
    line = invoice_preview(repository, TENANT, FEB_START, FEB_END)[0]
    assert (line.line_no, line.line_type, line.description) == (1, "plan", "GROWTH")
    assert line.amount == line.total == Decimal("149.00")


@pytest.mark.rule("INVOICING-R01")
def test_missing_subscription_is_not_found(client, monkeypatch) -> None:
    repository = FakeInvoicingRepository([])
    with pytest.raises(NoSubscriptionError):
        invoice_preview(repository, TENANT, FEB_START, FEB_END)
    with pytest.raises(NoSubscriptionError):
        issue_invoice(repository, TENANT, FEB_START, FEB_END)
    assert repository.writes == []

    def no_subscription(*_args: object) -> None:
        raise NoSubscriptionError(TENANT)

    monkeypatch.setattr(main, "invoice_preview", no_subscription)
    monkeypatch.setattr(main, "issue_invoice", no_subscription)
    preview = client.get(f"/api/tenants/{TENANT}/invoice-preview?{PREVIEW_QUERY}")
    issued = client.post(f"/api/tenants/{TENANT}/invoices", json=ISSUE_BODY)
    assert (preview.status_code, issued.status_code) == (404, 404)


@pytest.mark.rule("INVOICING-R02")
def test_usage_line_is_the_rounded_rating_overage() -> None:
    repository = FakeInvoicingRepository([subscription()], events=[usage(201)])
    line = invoice_preview(repository, TENANT, FEB_START, FEB_END)[1]
    # 101 * 0.055 + 0 * 0.0825 = 5.555 -> half away from zero
    assert (line.line_no, line.line_type, line.description) == (2, "usage", "usage overage")
    assert line.amount == line.total == Decimal("5.56")


@pytest.mark.rule("INVOICING-R03")
def test_tax_is_hard_coded_and_split_into_two_unrounded_halves() -> None:
    assert invoice_tax(Decimal("49.00"), Decimal("5.56"), True) == ZERO
    assert invoice_tax(Decimal("49.00"), Decimal("5.56"), False) == Decimal("4.501200")
    assert invoice_tax(Decimal("49.00"), Decimal("5.56"), None) == Decimal("4.501200")
    lines = preview_lines("STARTER", Decimal("49.00"), Decimal("5.56"), False, ZERO)
    assert [(item.line_type, item.description) for item in lines[2:4]] == [
        ("tax", "regional tax"),
        ("tax", "local tax"),
    ]
    assert lines[2].amount == lines[3].amount == lines[2].total == Decimal("2.2506")
    exempt = preview_lines("SCALE", Decimal("499.00"), Decimal("5.02"), True, ZERO)
    assert exempt[2].amount == exempt[3].amount == ZERO


@pytest.mark.rule("INVOICING-R04")
def test_preview_always_has_five_lines_with_zero_tax_amount() -> None:
    lines = invoice_preview(
        FakeInvoicingRepository([subscription()], notes=[note(NOTE_A, FEB_START, "10.00")]),
        TENANT,
        FEB_START,
        FEB_END,
    )
    assert [item.line_no for item in lines] == [1, 2, 3, 4, 5]
    assert [item.line_type for item in lines] == ["plan", "usage", "tax", "tax", "credit"]
    assert all(item.tax_amount == ZERO for item in lines)
    assert [item.credit_applied for item in lines] == [ZERO] * 4 + [Decimal("10.00")]


@pytest.mark.rule("INVOICING-R05")
def test_credit_uses_all_positive_notes_and_is_capped_by_the_rounded_gross() -> None:
    notes = [
        note(NOTE_A, date(2025, 6, 1), "5.00"),
        note(NOTE_B, date(2026, 3, 15), "25.00"),
        note(NOTE_C, date(2026, 1, 1), "0.00"),
    ]
    assert available_credit(notes) == Decimal("30.00")
    assert available_credit([]) == ZERO
    assert credit_applied(Decimal("30.00"), Decimal("499.00"), Decimal("5.02"), ZERO) == Decimal(
        "30.00"
    )
    # 49.00 + 0 + 4.0425 rounds to 53.04 before the cap is applied
    assert credit_applied(Decimal("60.00"), Decimal("49.00"), ZERO, Decimal("4.0425")) == Decimal(
        "53.04"
    )
    credit = preview_lines("STARTER", Decimal("49.00"), ZERO, False, Decimal("60.00"))[4]
    assert (credit.description, credit.amount, credit.credit_applied, credit.total) == (
        "credit notes",
        ZERO,
        Decimal("53.04"),
        Decimal("-53.04"),
    )
    assert preview_lines("STARTER", Decimal("49.00"), ZERO, False, ZERO)[4].total == ZERO


@pytest.mark.rule("INVOICING-R06")
def test_issue_finalizes_rating_and_upserts_a_deterministic_invoice() -> None:
    repository = FakeInvoicingRepository([subscription()], events=[usage(201)])
    issued = issue_invoice(repository, TENANT, FEB_START, FEB_END)
    period_id = rating_period_id(TENANT, FEB_START)
    invoice_id = legacy_md5_uuid(f"{period_id}invoice")
    assert invoice_id_for(period_id) == invoice_id
    assert rating_result_id(period_id) in repository.results
    assert issued.invoice.invoice_id == invoice_id
    assert issued.invoice.issued_at == datetime(2026, 2, 28, tzinfo=UTC)
    assert issued.invoice.status == "issued"
    assert issued.period_invoices == [issued.invoice]


@pytest.mark.rule("INVOICING-R06")
def test_reissue_only_resets_status_and_keeps_the_original_row() -> None:
    repository = FakeInvoicingRepository([subscription()])
    period_id = rating_period_id(TENANT, FEB_START)
    invoice_id = invoice_id_for(period_id)
    original_issue = datetime(2026, 3, 2, tzinfo=UTC)
    repository.invoices[invoice_id] = InvoiceRow(
        invoice_id, TENANT, period_id, original_issue, ZERO, ZERO, ZERO, "paid"
    )
    issued = issue_invoice(repository, TENANT, FEB_START, FEB_END)
    assert (issued.invoice.status, issued.invoice.issued_at) == ("issued", original_issue)


@pytest.mark.rule("INVOICING-R06")
def test_issue_maps_rating_errors(client) -> None:
    reversed_period = client.post(
        f"/api/tenants/{TENANT}/invoices",
        json={"period_start": "2026-02-28", "period_end": "2026-02-01"},
    )
    assert reversed_period.status_code == 422


@pytest.mark.rule("INVOICING-R07")
def test_issue_replaces_lines_with_deterministic_ids_and_rounded_amounts() -> None:
    repository = FakeInvoicingRepository(
        [subscription()], events=[usage(201)], notes=[note(NOTE_A, FEB_START, "10.00")]
    )
    issue_invoice(repository, TENANT, FEB_START, FEB_END)
    issue_invoice(repository, TENANT, FEB_START, FEB_END)
    invoice_id = invoice_id_for(rating_period_id(TENANT, FEB_START))
    rows = invoice_lines(repository.list_invoice_lines(invoice_id))
    assert len(rows) == 5
    assert [item.line_id for item in rows] == [invoice_line_id(invoice_id, n) for n in range(1, 6)]
    assert rows[0].line_id == legacy_md5_uuid(f"{invoice_id}1")
    assert [item.amount for item in rows] == [
        Decimal("49.00"),
        Decimal("5.56"),
        Decimal("2.25"),
        Decimal("2.25"),
        ZERO,
    ]


@pytest.mark.rule("INVOICING-R07")
def test_stored_credit_line_keeps_the_negative_total_and_rounds_half_away_from_zero() -> None:
    preview = [
        InvoicePreviewLine(
            3, "tax", "regional tax", Decimal("2.125"), ZERO, ZERO, Decimal("2.125")
        ),
        InvoicePreviewLine(
            5, "credit", "credit notes", ZERO, ZERO, Decimal("1.005"), Decimal("-1.005")
        ),
    ]
    rows = stored_lines(UUID(int=1), preview)
    assert [item.amount for item in rows] == [Decimal("2.13"), Decimal("-1.01")]


@pytest.mark.rule("INVOICING-R08")
def test_totals_sum_rounded_lines_and_round_total_after_credit() -> None:
    tenant_six = preview_lines("STARTER", Decimal("49.00"), Decimal("5.56"), False, ZERO)
    assert invoice_totals(tenant_six) == InvoiceTotals(
        Decimal("54.56"), Decimal("4.50"), ZERO, Decimal("59.06")
    )
    # per-half rounding: 0.18 * 0.0825 = 0.01485 -> halves 0.007425 -> 0.01 each
    small = preview_lines("TINY", Decimal("0.18"), ZERO, False, Decimal("100.00"))
    assert invoice_totals(small) == InvoiceTotals(
        Decimal("0.18"), Decimal("0.02"), Decimal("0.19"), Decimal("0.01")
    )
    credited = preview_lines("STARTER", Decimal("49.00"), ZERO, False, Decimal("60.00"))
    assert invoice_totals(credited).total == Decimal("0.00")


@pytest.mark.rule("INVOICING-R08")
def test_negative_total_is_a_conflict_and_writes_nothing(client, monkeypatch) -> None:
    repository = FakeInvoicingRepository(
        [subscription()],
        plans=[plan(STARTER, "STARTER", "55.15")],
        notes=[note(NOTE_A, FEB_START, "100.00")],
    )
    with pytest.raises(NegativeInvoiceTotalError):
        issue_invoice(repository, TENANT, FEB_START, FEB_END)
    assert repository.writes == []
    assert repository.notes[NOTE_A].remaining_amount == Decimal("100.00")

    def negative(*_args: object) -> None:
        raise NegativeInvoiceTotalError(Decimal("-0.01"))

    monkeypatch.setattr(main, "issue_invoice", negative)
    assert client.post(f"/api/tenants/{TENANT}/invoices", json=ISSUE_BODY).status_code == 409


@pytest.mark.rule("INVOICING-R09")
def test_credit_is_consumed_oldest_first_with_id_tiebreak() -> None:
    notes = [
        note(NOTE_B, FEB_START, "30.00"),
        note(NOTE_A, FEB_START, "30.00"),
        note(NOTE_C, date(2026, 1, 31), "0.00"),
    ]
    assert consume_credit(notes, Decimal("53.04")) == [
        (NOTE_A, Decimal("0.00")),
        (NOTE_B, Decimal("6.96")),
    ]
    assert consume_credit(notes, ZERO) == []


@pytest.mark.rule("INVOICING-R09")
def test_reissue_consumes_remaining_credit_again() -> None:
    repository = FakeInvoicingRepository(
        [subscription()],
        notes=[note(NOTE_A, date(2026, 1, 31), "5.00"), note(NOTE_B, FEB_START, "55.00")],
    )
    first = issue_invoice(repository, TENANT, FEB_START, FEB_END)
    assert [item.remaining_amount for item in first.credit_notes] == [
        Decimal("0.00"),
        Decimal("6.96"),
    ]
    assert (first.invoice.tax, first.invoice.total) == (Decimal("4.04"), Decimal("0.00"))
    second = issue_invoice(repository, TENANT, FEB_START, FEB_END)
    assert [item.remaining_amount for item in second.credit_notes] == [ZERO, Decimal("0.00")]
    assert second.invoice.total == Decimal("46.08")


@pytest.mark.rule("INVOICING-R09")
def test_credit_notes_are_locked_before_the_invoice_is_priced() -> None:
    repository = FakeInvoicingRepository(
        [subscription()], notes=[note(NOTE_A, date(2026, 1, 31), "5.00")]
    )
    issue_invoice(repository, TENANT, FEB_START, FEB_END)
    assert repository.locked_before_reads == [True]


@pytest.mark.rule("INVOICING-R10")
def test_invoice_lines_are_returned_in_line_order(client, monkeypatch) -> None:
    invoice_id = UUID("60000000-0000-0000-0000-000000000001")
    rows = [
        InvoiceLineRow(UUID(int=2), invoice_id, 2, "usage", "usage overage", Decimal("12.29")),
        InvoiceLineRow(UUID(int=1), invoice_id, 1, "plan", "GROWTH", Decimal("149.00")),
    ]
    assert [item.line_no for item in invoice_lines(rows)] == [1, 2]

    class Repository:
        def __init__(self, _connection: object) -> None:
            pass

        def list_invoice_lines(self, requested: UUID) -> list[InvoiceLineRow]:
            return rows if requested == invoice_id else []

    monkeypatch.setattr(main, "PostgresInvoicingRepository", Repository)
    known = client.get(f"/api/invoices/{invoice_id}/lines")
    unknown = client.get(f"/api/invoices/{UUID(int=99)}/lines")
    assert known.status_code == 200
    assert [(item["line_type"], item["amount"]) for item in known.json()] == [
        ("plan", "149.00"),
        ("usage", "12.29"),
    ]
    assert (unknown.status_code, unknown.json()) == (200, [])
