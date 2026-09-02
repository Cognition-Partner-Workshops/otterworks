"""App-side port of OW_BILLING.PKG_INVOICING (mapping D10, unit U8)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from bson import Decimal128
from pymongo import ASCENDING

from . import NS_VALUE, rating, util

TAX_RATE = Decimal("0.0825")
INV_STATUS_ISSUED = 20


@dataclass(frozen=True)
class InvoicingStore(rating.RatingStore):
    """Collections read and written by the invoicing module."""

    @property
    def billing_invoices(self):
        return self.coll("billing_invoices")

    @property
    def credit_notes(self):
        return self.coll("credit_notes")

    @property
    def tenants(self):
        return self.coll("tenants")


class InvoicingIntegrityError(RuntimeError):
    """ORA-01400: an invoice column would receive NULL."""


@dataclass(frozen=True)
class Preview:
    plan_code: str | None
    plan_fee: Decimal | None
    overage: Decimal | None
    tax: Decimal | None
    credit: Decimal


def to_decimal(value: Any) -> rating.Number:
    return rating.to_decimal(value)


def _add(a: rating.Number, b: rating.Number) -> rating.Number:
    return rating._add(a, b)


def _mul(a: rating.Number, b: rating.Number) -> rating.Number:
    return rating._mul(a, b)


def oracle_round(value: rating.Number, places: int = 0) -> rating.Number:
    return rating.oracle_round(value, places)


def _nvl(value: rating.Number, default: rating.Number) -> rating.Number:
    return rating.nvl(value, default)


def _least(*values: rating.Number) -> rating.Number:
    return rating.least(*values)


def _greatest(*values: rating.Number) -> rating.Number:
    return rating.greatest(*values)


def _to_char(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"-0", "-0.0"}:
        return "0"
    if text.startswith("0."):
        text = text[1:]
    elif text.startswith("-0."):
        text = "-" + text[2:]
    return text


def log_msg(store: rating.RatingStore, module: str, message: str) -> None:
    rating.log_msg(store, module, message)


def _positive_credit_notes(
    store: InvoicingStore, tenant_id: str, *, oldest_first: bool = False
) -> list[dict[str, Any]]:
    notes = [
        note
        for note in store.credit_notes.find({"tenant_id": tenant_id})
        if (to_decimal(note.get("remaining_amount")) or Decimal(0)) > 0
    ]
    if oldest_first:
        notes.sort(key=lambda note: (note["issued_on"], str(note.get("_id"))))
    return notes


def compute_preview(
    store: InvoicingStore,
    tenant_id: str,
    period_start: date,
    period_end: date,
) -> Preview:
    p_start, p_end = rating.as_datetime(period_start), rating.as_datetime(period_end)
    sub = rating.covering_subscription(store, tenant_id, p_start, p_end)
    plan = store.plans.find_one({"_id": sub["plan_id"]}) if sub else None
    if plan is None:
        plan_code = None
        plan_fee = None
    else:
        plan_code = plan["code"]
        plan_fee = to_decimal(plan["monthly_fee"])

    overage = rating.compute_rating(
        store, tenant_id, period_start, period_end
    ).overage_amount

    credit = Decimal(0)
    for note in _positive_credit_notes(store, tenant_id):
        credit += _nvl(to_decimal(note.get("remaining_amount")), Decimal(0)) or Decimal(0)

    tenant = store.tenants.find_one({"_id": tenant_id})
    exempt = tenant.get("tax_exempt_yn", "N") if tenant else "N"
    tax = (
        Decimal(0)
        if exempt == "Y"
        else _mul(_add(plan_fee, overage), TAX_RATE)
    )
    return Preview(plan_code, plan_fee, overage, tax, credit)


def fn_invoice_preview(
    store: InvoicingStore,
    tenant_id: str,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    preview = compute_preview(store, tenant_id, period_start, period_end)
    charge_cap = oracle_round(
        _add(_add(preview.plan_fee, preview.overage), preview.tax), 2
    )
    credit_app = _least(preview.credit, _nvl(charge_cap, preview.credit))
    half_tax = None if preview.tax is None else preview.tax / 2
    return [
        {
            "line_no": 1,
            "line_type": "plan",
            "description": preview.plan_code,
            "amount": oracle_round(preview.plan_fee, 2),
            "tax_amount": Decimal(0),
            "credit_applied": Decimal(0),
            "total": oracle_round(preview.plan_fee, 2),
        },
        {
            "line_no": 2,
            "line_type": "usage",
            "description": "usage overage",
            "amount": oracle_round(preview.overage, 2),
            "tax_amount": Decimal(0),
            "credit_applied": Decimal(0),
            "total": oracle_round(preview.overage, 2),
        },
        {
            "line_no": 3,
            "line_type": "tax",
            "description": "regional tax",
            "amount": half_tax,
            "tax_amount": Decimal(0),
            "credit_applied": Decimal(0),
            "total": half_tax,
        },
        {
            "line_no": 4,
            "line_type": "tax",
            "description": "local tax",
            "amount": half_tax,
            "tax_amount": Decimal(0),
            "credit_applied": Decimal(0),
            "total": half_tax,
        },
        {
            "line_no": 5,
            "line_type": "credit",
            "description": "credit notes",
            "amount": Decimal(0),
            "tax_amount": Decimal(0),
            "credit_applied": credit_app,
            "total": None if credit_app is None else -credit_app,
        },
    ]


def sp_issue_invoice(
    store: InvoicingStore,
    tenant_id: str,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    period_id = util.f_md5_uuid(f"{tenant_id}{period_start:%Y-%m-%d}")
    invoice_id = util.f_md5_uuid(period_id + "invoice")

    rating.sp_finalize_rating(store, tenant_id, period_start, period_end)
    preview_rows = fn_invoice_preview(store, tenant_id, period_start, period_end)

    lines = []
    for row in preview_rows:
        amount = row["total"] if row["line_type"] == "credit" else row["amount"]
        amount = oracle_round(amount, 2)
        if row["description"] is None or amount is None:
            column = "description" if row["description"] is None else "amount"
            raise InvoicingIntegrityError(
                f"invoice_lines.{column} cannot be NULL "
                f"(tenant={tenant_id} invoice={invoice_id})"
            )
        lines.append(
            {
                "id": util.f_md5_uuid(invoice_id + str(row["line_no"])),
                "line_no": row["line_no"],
                "line_type": row["line_type"],
                "description": row["description"],
                "amount": Decimal128(amount),
            }
        )

    subtotal: rating.Number = Decimal(0)
    tax: rating.Number = Decimal(0)
    credit: rating.Number = Decimal(0)
    for row in preview_rows:
        if row["line_type"] in {"plan", "usage"}:
            subtotal = _add(subtotal, oracle_round(row["amount"], 2))
        elif row["line_type"] == "tax":
            tax = _add(tax, oracle_round(row["amount"], 2))
        elif row["line_type"] == "credit":
            credit = row["credit_applied"]
    total = oracle_round(
        _add(_add(subtotal, tax), None if credit is None else -credit), 2
    )
    if subtotal is None or tax is None or credit is None or total is None:
        raise InvoicingIntegrityError(
            f"invoices.amount cannot be NULL (tenant={tenant_id} invoice={invoice_id})"
        )

    existing = store.billing_invoices.find_one({"_id": invoice_id})
    if existing is None:
        tenant_value = tenant_id
        period_value = period_id
        issued_at = rating.as_datetime(period_end)
    else:
        tenant_value = existing["tenant_id"]
        period_value = existing["period_id"]
        issued_at = existing["issued_at"]
    doc = {
        "_id": invoice_id,
        "id": invoice_id,
        "tenant_id": tenant_value,
        "period_id": period_value,
        "issued_at": issued_at,
        "subtotal": Decimal128(oracle_round(subtotal, 2)),
        "tax": Decimal128(oracle_round(tax, 2)),
        "total": Decimal128(total),
        "status_cd": INV_STATUS_ISSUED,
        "lines": lines,
        "ns": NS_VALUE,
    }
    store.billing_invoices.replace_one({"_id": invoice_id}, doc, upsert=True)

    v_credit = credit
    notes = _positive_credit_notes(store, tenant_id, oldest_first=True)
    for note in notes:
        if v_credit <= 0:
            break
        remaining = to_decimal(note.get("remaining_amount"))
        if remaining is None:
            continue
        updated = _greatest(_add(remaining, -v_credit), Decimal(0))
        store.credit_notes.update_one(
            {"_id": note["_id"]},
            {"$set": {"remaining_amount": Decimal128(oracle_round(updated, 2))}},
        )
        v_credit = _greatest(v_credit - remaining, Decimal(0))

    log_msg(
        store,
        "INVOICING",
        f"issued invoice={invoice_id} total={_to_char(_nvl(total, Decimal(0)))}",
    )
    return store.billing_invoices.find_one({"_id": invoice_id})


def fn_invoice_lines(store: InvoicingStore, invoice_id: str) -> list[dict[str, Any]]:
    doc = store.billing_invoices.find_one({"_id": invoice_id})
    if doc is None:
        return []
    return [
        {
            "line_no": line["line_no"],
            "line_type": line["line_type"],
            "description": line["description"],
            "amount": to_decimal(line["amount"]),
        }
        for line in sorted(doc.get("lines", []), key=lambda line: line["line_no"])
    ]


def invoice_state_rows(
    store: InvoicingStore, tenant_id: str, period_start: date
) -> list[dict[str, Any]]:
    period_id = util.f_md5_uuid(f"{tenant_id}{period_start:%Y-%m-%d}")
    status = {10: "draft", 20: "issued", 30: "paid", 40: "overdue"}
    return [
        {
            "status": status.get(row.get("status_cd"), "unknown"),
            "subtotal": to_decimal(row.get("subtotal")),
            "tax": to_decimal(row.get("tax")),
            "total": to_decimal(row.get("total")),
        }
        for row in store.billing_invoices.find(
            {"tenant_id": tenant_id, "period_id": period_id}
        )
    ]


def credit_note_rows(store: InvoicingStore, tenant_id: str) -> list[dict[str, Any]]:
    rows = store.credit_notes.find({"tenant_id": tenant_id}).sort(
        [("issued_on", ASCENDING), ("_id", ASCENDING)]
    )
    return [
        {
            "id": row.get("id", row.get("_id")),
            "issued_on": (
                row["issued_on"].date()
                if isinstance(row["issued_on"], datetime)
                else row["issued_on"]
            ),
            "remaining_amount": to_decimal(row.get("remaining_amount")),
        }
        for row in rows
    ]
