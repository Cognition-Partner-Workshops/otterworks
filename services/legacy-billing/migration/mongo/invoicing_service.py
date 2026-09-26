#!/usr/bin/env python3
"""Unit u-10-plsql-invoicing: PKG_INVOICING ported to the MongoDB service
model.

Port of services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql.
The g_* preview globals collapse into the dict from compute_preview().
Invoice lines embed into `invoices.lines` per the mapping spec (the spec
embeds INVOICE_LINES under the parent invoice document; sp_issue_invoice
rewrites the array atomically with the invoice).

Reads: subscriptions, plans, tenants, creditNotes (and rating via
rating_service). Writes (sp_issue_invoice only): invoices (single-document
replace incl. embedded lines), ratingPeriods/ratingResults via
finalize_rating, creditNotes burn-down, billingAuditLog.
"""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Any

import ow_util
import rating_service
from plans_service import _latest_covering_sub, _utc

TAX_RATE = Decimal("0.0825")  # hardcoded 2011 combined rate


def _dec(v) -> Decimal | None:
    if v is None:
        return None
    return v.to_decimal() if hasattr(v, "to_decimal") else Decimal(str(v))


def _dec128(d: Decimal | None):
    if d is None:
        return None
    from bson import Decimal128  # lazy

    return Decimal128(str(d))


def compute_preview(db, tenant_id: str, period_start: _dt.date,
                    period_end: _dt.date) -> dict[str, Any]:
    """pkg_invoicing.compute_preview -> {plan_code, plan_fee, overage, tax, credit}."""
    g = {"plan_code": None, "plan_fee": None, "overage": None,
         "tax": None, "credit": Decimal(0)}

    sub = _latest_covering_sub(db, tenant_id, period_start, period_end)
    if sub:
        plan = db["plans"].find_one({"_id": sub.get("planId")})
        if plan:
            g["plan_code"] = plan.get("code")
            g["plan_fee"] = _dec(plan.get("monthlyFee"))

    r = rating_service.compute_rating(db, tenant_id, period_start, period_end)
    g["overage"] = r["overage_amount"]

    for cn in db["creditNotes"].find(
        {"tenantId": tenant_id, "remainingAmount": {"$gt": 0}},
        projection={"remainingAmount": 1},
    ):
        g["credit"] += _dec(cn.get("remainingAmount")) or Decimal(0)

    tenant = db["tenants"].find_one({"_id": tenant_id}, projection={"taxExempt": 1})
    exempt = bool(tenant and tenant.get("taxExempt"))
    # NULL plan fee / overage propagates to NULL tax, like the Postgres
    # original's (fee + overage) * rate.
    g["tax"] = (
        Decimal(0)
        if exempt
        else (
            None
            if g["plan_fee"] is None or g["overage"] is None
            else (g["plan_fee"] + g["overage"]) * TAX_RATE
        )
    )
    return g


def _preview_lines(g: dict) -> list[dict[str, Any]]:
    """The fixed 5-row UNION ALL of fn_invoice_preview, unrendered
    (Decimal amounts; renderers format per the transcript)."""
    fee, ovg, tax, credit = g["plan_fee"], g["overage"], g["tax"], g["credit"]
    cap = (
        None
        if fee is None or ovg is None or tax is None
        else ow_util.money_round(fee + ovg + tax, 2)
    )
    # LEAST ignores NULL caps in the Postgres original.
    credit_app = min(credit, cap if cap is not None else credit)
    half_tax = None if tax is None else tax / 2
    return [
        {"line_no": 1, "line_type": "plan", "description": g["plan_code"],
         "amount": None if fee is None else ow_util.money_round(fee, 2),
         "tax_amount": Decimal(0), "credit_applied": Decimal(0),
         "total": None if fee is None else ow_util.money_round(fee, 2)},
        {"line_no": 2, "line_type": "usage", "description": "usage overage",
         "amount": None if ovg is None else ow_util.money_round(ovg, 2),
         "tax_amount": Decimal(0), "credit_applied": Decimal(0),
         "total": None if ovg is None else ow_util.money_round(ovg, 2)},
        {"line_no": 3, "line_type": "tax", "description": "regional tax",
         "amount": half_tax, "tax_amount": Decimal(0),
         "credit_applied": Decimal(0), "total": half_tax},
        {"line_no": 4, "line_type": "tax", "description": "local tax",
         "amount": half_tax, "tax_amount": Decimal(0),
         "credit_applied": Decimal(0), "total": half_tax},
        {"line_no": 5, "line_type": "credit", "description": "credit notes",
         "amount": Decimal(0), "tax_amount": Decimal(0),
         "credit_applied": credit_app, "total": -credit_app},
    ]


def invoice_preview(db, tenant_id: str, period_start: _dt.date,
                    period_end: _dt.date) -> list[dict[str, Any]]:
    """pkg_invoicing.fn_invoice_preview, transcript-rendered."""
    g = compute_preview(db, tenant_id, period_start, period_end)
    return [
        {
            "line_no": l["line_no"],
            "line_type": l["line_type"],
            "description": l["description"],
            "amount": ow_util.dec2(l["amount"]),
            "tax_amount": ow_util.dec2(l["tax_amount"]),
            "credit_applied": ow_util.dec2(l["credit_applied"]),
            "total": ow_util.dec2(l["total"]),
        }
        for l in _preview_lines(g)
    ]


def invoice_lines(db, invoice_id: str) -> list[dict[str, Any]]:
    """pkg_invoicing.fn_invoice_lines over the embedded lines array."""
    inv = db["invoices"].find_one({"_id": invoice_id})
    rows = []
    for l in sorted((inv or {}).get("lines", []), key=lambda x: x.get("lineNo", 0)):
        rows.append(
            {
                "line_no": l.get("lineNo"),
                "line_type": l.get("lineType"),
                "description": l.get("description"),
                "amount": ow_util.dec2(l.get("amount")),
            }
        )
    return rows


def issue_invoice(db, tenant_id: str, period_start: _dt.date,
                  period_end: _dt.date) -> None:
    """pkg_invoicing.sp_issue_invoice: single-document invoice replace +
    credit-note burn-down."""
    period_id = ow_util.md5_uuid(tenant_id + period_start.isoformat())
    invoice_id = ow_util.md5_uuid(period_id + "invoice")

    rating_service.finalize_rating(db, tenant_id, period_start, period_end)

    if db["invoices"].count_documents({"_id": invoice_id}) == 0:
        db["invoices"].insert_one(
            {
                "_id": invoice_id,
                "tenantId": tenant_id,
                "periodId": period_id,
                "issuedAt": _utc(period_end),
                "subtotal": _dec128(Decimal(0)),
                "tax": _dec128(Decimal(0)),
                "total": _dec128(Decimal(0)),
                "statusCd": 20,
                "lines": [],
            }
        )
    else:
        db["invoices"].update_one({"_id": invoice_id},
                                  {"$set": {"statusCd": 20}})

    # Lines rebuilt from scratch on every issue.
    g = compute_preview(db, tenant_id, period_start, period_end)
    lines = []
    subtotal = tax_amt = Decimal(0)
    credit = Decimal(0)
    for l in _preview_lines(g):
        stored = l["total"] if l["line_type"] == "credit" else l["amount"]
        lines.append(
            {
                "id": ow_util.md5_uuid(invoice_id + str(l["line_no"])),
                "lineNo": l["line_no"],
                "lineType": l["line_type"],
                "description": l["description"],
                "amount": _dec128(stored),
            }
        )
        if l["line_type"] in ("plan", "usage"):
            subtotal += ow_util.money_round(l["amount"], 2) or Decimal(0)
        elif l["line_type"] == "tax":
            tax_amt += ow_util.money_round(l["amount"], 2) or Decimal(0)
        elif l["line_type"] == "credit":
            credit = l["credit_applied"]

    total = ow_util.money_round(subtotal + tax_amt - credit, 2)
    db["invoices"].update_one(
        {"_id": invoice_id},
        {
            "$set": {
                "lines": lines,
                "subtotal": _dec128(ow_util.money_round(subtotal, 2)),
                "tax": _dec128(ow_util.money_round(tax_amt, 2)),
                "total": _dec128(total),
            }
        },
    )

    # Burn down credit notes oldest-first with the same running counter.
    for cn in db["creditNotes"].find(
        {"tenantId": tenant_id, "remainingAmount": {"$gt": 0}}
    ).sort([("issuedOn", 1), ("_id", 1)]):
        if credit <= 0:
            break
        rem = _dec(cn.get("remainingAmount")) or Decimal(0)
        db["creditNotes"].update_one(
            {"_id": cn["_id"]},
            {"$set": {"remainingAmount": _dec128(max(rem - credit, Decimal(0)))}},
        )
        credit = max(credit - rem, Decimal(0))

    ow_util.log_msg(db, "INVOICING", f"issued invoice={invoice_id} total={total or 0}")
