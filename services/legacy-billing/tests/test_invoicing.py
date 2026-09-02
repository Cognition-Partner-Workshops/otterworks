"""Unit tests for the PKG_INVOICING port (ow_billing.invoicing)."""

# ruff: noqa: DTZ001
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import mongomock
import pytest
from bson import Decimal128, Int64

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from ow_billing import NS_VALUE, invoicing, util

TENANT = "00000000-0000-0000-0000-000000000001"
FEB1, FEB28 = date(2026, 2, 1), date(2026, 2, 28)
MAR1, MAR31 = date(2026, 3, 1), date(2026, 3, 31)


@pytest.fixture(autouse=True)
def _disable_mongomock_transactions(monkeypatch):
    monkeypatch.setattr(invoicing, "_with_transaction", lambda store, fn: fn(None))


def _store() -> invoicing.InvoicingStore:
    store = invoicing.InvoicingStore(
        mongomock.MongoClient()["ow_tp_mongodb_205236"], "replay_u8_"
    )
    store.rating_periods.create_index(
        [("tenant_id", 1), ("period_start", 1)], unique=True
    )
    store.counters.insert_one(
        {
            "_id": util.SEQ_BILLING_AUDIT_LOG,
            "seq": Int64(0),
            "source_sequence": "SEQ_BILLING_AUDIT_LOG",
            "ns": NS_VALUE,
        }
    )
    return store


def _tenant(store, tenant_id=TENANT, exempt="N"):
    store.tenants.insert_one(
        {
            "_id": tenant_id,
            "id": tenant_id,
            "tax_exempt_yn": exempt,
            "ns": NS_VALUE,
        }
    )


def _plan(store, *, code="PRO", fee="49.00", included=100, rate="0.0556"):
    store.plans.insert_one(
        {
            "_id": "plan-1",
            "id": "plan-1",
            "code": code,
            "monthly_fee": Decimal128(fee),
            "included_units": Int64(included),
            "overage_rate": Decimal128(rate),
            "ns": NS_VALUE,
        }
    )


def _subscription(store, tenant_id=TENANT):
    store.subscriptions.insert_one(
        {
            "_id": "sub-1",
            "id": "sub-1",
            "tenant_id": tenant_id,
            "plan_id": "plan-1",
            "starts_on": datetime(2026, 1, 1),
            "ends_on": None,
            "status_cd": 10,
            "suspended_on": None,
            "ns": NS_VALUE,
        }
    )


def _usage(store, units=200):
    store.usage_events.insert_one(
        {
            "_id": "event-1",
            "id": "event-1",
            "tenant_id": TENANT,
            "occurred_at": datetime(2026, 2, 10),
            "units": Int64(units),
            "kind_cd": 1,
            "ns": NS_VALUE,
        }
    )


def _credit(store, ident, amount, issued_on=datetime(2026, 2, 1)):
    store.credit_notes.insert_one(
        {
            "_id": ident,
            "id": ident,
            "tenant_id": TENANT,
            "issued_on": issued_on,
            "amount": Decimal128(str(amount)),
            "remaining_amount": Decimal128(str(amount)),
            "ns": NS_VALUE,
        }
    )


def test_preview_rounds_charges_but_preserves_exact_tax_halves():
    store = _store()
    _tenant(store)
    _plan(store)
    _subscription(store)
    _usage(store)
    _credit(store, "credit-1", "60.00")

    preview = invoicing.compute_preview(store, TENANT, FEB1, FEB28)
    assert preview.plan_code == "PRO"
    assert preview.plan_fee == Decimal("49.00")
    assert preview.overage == Decimal("5.56")
    assert preview.tax == Decimal("4.501200")
    assert preview.credit == Decimal("60.00")

    rows = invoicing.fn_invoice_preview(store, TENANT, FEB1, FEB28)
    assert len(rows) == 5
    assert rows[0]["amount"] == Decimal("49.00")
    assert rows[1]["amount"] == Decimal("5.56")
    assert rows[2]["amount"] == rows[3]["amount"] == Decimal("2.250600")
    assert rows[2]["amount"] == rows[2]["total"]
    assert rows[4]["credit_applied"] == Decimal("59.06")


def test_exempt_tenant_has_zero_tax_even_without_a_plan():
    store = _store()
    _tenant(store, exempt="Y")
    rows = invoicing.fn_invoice_preview(store, TENANT, FEB1, FEB28)

    assert rows[2]["amount"] == rows[3]["amount"] == Decimal(0)
    assert rows[2]["total"] == Decimal(0)
    assert invoicing.compute_preview(store, TENANT, FEB1, FEB28).tax == Decimal(0)


def test_no_subscription_keeps_plan_and_tax_null_and_applies_full_credit():
    store = _store()
    _tenant(store)
    _credit(store, "credit-1", "12.34")

    preview = invoicing.compute_preview(store, TENANT, FEB1, FEB28)
    rows = invoicing.fn_invoice_preview(store, TENANT, FEB1, FEB28)
    assert preview.plan_code is None and preview.plan_fee is None
    assert preview.overage is None and preview.tax is None
    assert rows[0]["description"] is None and rows[0]["amount"] is None
    assert rows[1]["amount"] is None
    assert rows[2]["amount"] is None and rows[3]["amount"] is None
    assert rows[4]["credit_applied"] == Decimal("12.34")


def test_issue_invoice_rebuilds_lines_and_preserves_existing_issue_metadata():
    store = _store()
    _tenant(store)
    _plan(store)
    _subscription(store)
    _usage(store)

    first = invoicing.sp_issue_invoice(store, TENANT, FEB1, FEB28)
    period_id = util.f_md5_uuid(f"{TENANT}2026-02-01")
    invoice_id = util.f_md5_uuid(period_id + "invoice")
    assert first["_id"] == first["id"] == invoice_id
    assert first["period_id"] == period_id
    assert first["subtotal"] == Decimal128("54.56")
    assert first["tax"] == Decimal128("4.50")
    assert first["total"] == Decimal128("59.06")
    assert first["status_cd"] == 20
    assert first["ns"] == NS_VALUE
    assert first["issued_at"] == datetime(2026, 2, 28)
    assert [line["id"] for line in first["lines"]] == [
        util.f_md5_uuid(invoice_id + str(number)) for number in range(1, 6)
    ]
    assert all(line["invoice_id"] == invoice_id for line in first["lines"])
    assert store.rating_periods.count_documents({}) == 1

    issued_at = first["issued_at"]
    store.billing_invoices.update_one(
        {"_id": invoice_id}, {"$set": {"lines": [{"line_no": 99}]}}
    )
    second = invoicing.sp_issue_invoice(store, TENANT, FEB1, FEB28)
    assert store.billing_invoices.count_documents({}) == 1
    assert second["issued_at"] == issued_at
    assert [line["line_no"] for line in second["lines"]] == [1, 2, 3, 4, 5]
    assert store.rating_periods.count_documents({}) == 1


def test_credit_burn_down_preserves_the_legacy_running_counter_quirk():
    store = _store()
    _tenant(store)
    _plan(store, rate="0.0000")
    _subscription(store)
    _usage(store, units=100)
    _credit(store, "older", "5.00", datetime(2026, 1, 31))
    _credit(store, "newer", "55.00", datetime(2026, 2, 1))

    first = invoicing.sp_issue_invoice(store, TENANT, FEB1, FEB28)
    assert first["total"] == Decimal128("0.00")
    assert store.credit_notes.find_one({"_id": "older"})["remaining_amount"] == Decimal128(
        "0.00"
    )
    assert store.credit_notes.find_one({"_id": "newer"})["remaining_amount"] == Decimal128(
        "6.96"
    )

    second = invoicing.sp_issue_invoice(store, TENANT, FEB1, FEB28)
    assert second["lines"][4]["amount"] == Decimal128("-6.96")
    assert store.credit_notes.find_one({"_id": "newer"})["remaining_amount"] == Decimal128(
        "0.00"
    )


def test_credit_burn_down_is_serialized_between_periods():
    store = _store()
    _tenant(store)
    _plan(store)
    _subscription(store)
    _usage(store)
    _credit(store, "shared", "60.00")

    first = invoicing.sp_issue_invoice(store, TENANT, FEB1, FEB28)
    second = invoicing.sp_issue_invoice(store, TENANT, MAR1, MAR31)

    first_credit = -first["lines"][4]["amount"].to_decimal()
    second_credit = -second["lines"][4]["amount"].to_decimal()
    assert first_credit == Decimal("59.06")
    assert second_credit == Decimal("0.94")
    assert first_credit + second_credit == Decimal("60.00")
    assert store.credit_notes.find_one({"_id": "shared"})["remaining_amount"] == Decimal128(
        "0.00"
    )


def test_credit_burn_down_rejects_a_concurrent_change(monkeypatch):
    store = _store()
    _tenant(store)
    _plan(store)
    _subscription(store)
    _usage(store)
    _credit(store, "credit-1", "60.00")
    monkeypatch.setattr(
        store.credit_notes,
        "update_one",
        lambda *args, **kwargs: SimpleNamespace(matched_count=0),
    )

    with pytest.raises(RuntimeError, match="credit note changed concurrently"):
        invoicing.sp_issue_invoice(store, TENANT, FEB1, FEB28)


def test_credit_application_retries_from_the_current_balance(monkeypatch):
    store = _store()
    _tenant(store)
    _plan(store)
    _subscription(store)
    _usage(store)
    _credit(store, "shared", "60.00")

    def retry_with_reduced_credit(store, fn):
        fn(None)
        store.credit_notes.update_one(
            {"_id": "shared"},
            {"$set": {"remaining_amount": Decimal128("0.50")}},
        )
        return fn(None)

    monkeypatch.setattr(invoicing, "_with_transaction", retry_with_reduced_credit)
    invoice = invoicing.sp_issue_invoice(store, TENANT, FEB1, FEB28)

    assert invoice["lines"][4]["amount"] == Decimal128("-0.50")
    assert invoice["total"] == Decimal128("58.56")
    remaining = store.credit_notes.find_one({"_id": "shared"})["remaining_amount"]
    assert remaining == Decimal128("0.00")
    assert -invoice["lines"][4]["amount"].to_decimal() <= Decimal("60.00")


def test_invoice_lines_are_ordered_and_missing_invoice_is_empty():
    store = _store()
    store.billing_invoices.insert_one(
        {
            "_id": "invoice-1",
            "lines": [
                {
                    "line_no": 2,
                    "line_type": "usage",
                    "description": "usage",
                    "amount": Decimal128("2.00"),
                },
                {
                    "line_no": 1,
                    "line_type": "plan",
                    "description": "PRO",
                    "amount": Decimal128("49.00"),
                },
            ],
        }
    )
    assert [row["line_no"] for row in invoicing.fn_invoice_lines(store, "invoice-1")] == [
        1,
        2,
    ]
    assert invoicing.fn_invoice_lines(store, "missing") == []


def test_integrity_error_happens_before_invoice_or_credit_writes():
    store = _store()
    _tenant(store)
    _plan(store, code=None)
    _subscription(store)
    _usage(store)
    _credit(store, "credit-1", "12.00")

    with pytest.raises(invoicing.InvoicingIntegrityError, match="description"):
        invoicing.sp_issue_invoice(store, TENANT, FEB1, FEB28)
    assert store.billing_invoices.count_documents({}) == 0
    assert store.credit_notes.find_one({"_id": "credit-1"})["remaining_amount"] == Decimal128(
        "12.00"
    )


def test_to_char_matches_oracle_number_formatting():
    assert invoicing._to_char(Decimal("0.5")) == ".5"
    assert invoicing._to_char(Decimal(0)) == "0"
    assert invoicing._to_char(Decimal("59.0600")) == "59.06"
    assert invoicing._to_char(Decimal("-0.5")) == "-.5"
