from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Path, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.db import connect, migrate, reset
from app.domain import (
    CreditNoteRow,
    InvoicePreviewLine,
    InvoiceRow,
    NegativeInvoiceTotalError,
    NoSubscriptionError,
    RatingResultRow,
    UsageRating,
    catalog,
    change_plan,
    entitlement,
    finalize_rating,
    invoice_lines,
    invoice_preview,
    issue_invoice,
    rate_usage,
    usage_summary,
)
from app.repository import (
    PostgresInvoicingRepository,
    PostgresPlansRepository,
    PostgresRatingRepository,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    migrate()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanChange(BaseModel):
    plan_id: UUID
    effective_on: date


class RatingFinalization(BaseModel):
    period_start: date
    period_end: date


class InvoiceIssue(BaseModel):
    period_start: date
    period_end: date


NO_SUBSCRIPTION = "no subscription overlaps the rating period"


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with connect() as connection:
            connection.execute("SELECT 1")
    except psycopg.Error as error:
        raise HTTPException(status_code=503, detail="database unavailable") from error
    return {"status": "healthy", "service": settings.app_name}


@app.post("/internal/reset", status_code=204)
def internal_reset() -> Response:
    if not settings.allow_internal_reset:
        raise HTTPException(status_code=404, detail="internal reset is disabled")
    reset()
    return Response(status_code=204)


@app.get("/api/plans")
def list_plans() -> list[dict]:
    with connect() as connection:
        plans = catalog(PostgresPlansRepository(connection).list_plans())
    return [
        {
            "plan_id": str(plan.plan_id),
            "code": plan.code,
            "tier": plan.tier,
            "monthly_fee": f"{plan.monthly_fee:.2f}",
            "included_units": plan.included_units,
            "overage_rate": f"{plan.overage_rate:.6f}",
        }
        for plan in plans
    ]


@app.get("/api/tenants/{tenant_id}/entitlement")
def get_entitlement(
    tenant_id: Annotated[UUID, Path()],
    on: Annotated[date, Query()],
) -> dict:
    with connect() as connection:
        row = entitlement(
            PostgresPlansRepository(connection).find_entitlements(tenant_id),
            tenant_id,
            on,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="entitlement not found")
    return {
        "tenant_id": str(row.tenant_id),
        "plan_code": row.plan_code,
        "tier": row.tier,
        "monthly_fee": f"{row.monthly_fee:.2f}",
        "included_units": row.included_units,
        "subscription_status": row.subscription_status,
        "effective_on": max(row.starts_on, on).isoformat(),
    }


@app.post("/api/tenants/{tenant_id}/plan-change")
def change_tenant_plan(tenant_id: Annotated[UUID, Path()], request: PlanChange) -> dict:
    try:
        with connect() as connection:
            repository = PostgresPlansRepository(connection)
            subscriptions, created = change_plan(
                repository,
                tenant_id,
                request.plan_id,
                request.effective_on,
            )
            return {
                "latest_plan": str(created.plan_id),
                "latest_start": created.starts_on.isoformat(),
                "subscriptions": [
                    {
                        "plan_id": str(item.plan_id),
                        "starts_on": item.starts_on.isoformat(),
                        "ends_on": item.ends_on.isoformat() if item.ends_on else None,
                        "status": item.status,
                    }
                    for item in subscriptions
                ],
            }
    except psycopg.errors.ForeignKeyViolation as error:
        raise HTTPException(status_code=400, detail="invalid plan change") from error
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(
            status_code=409,
            detail="this plan change has already been requested",
        ) from error


def _usage_rating_body(rating: UsageRating) -> dict:
    return {
        "tenant_id": str(rating.tenant_id),
        "period_start": rating.period_start.isoformat(),
        "period_end": rating.period_end.isoformat(),
        "used_units": rating.used_units,
        "quota_units": rating.quota_units,
        "rollover_units": rating.rollover_units,
        "billable_units": rating.billable_units,
        "first_tier_units": rating.first_tier_units,
        "second_tier_units": rating.second_tier_units,
        "overage_amount": f"{rating.overage_amount:.2f}",
    }


def _rating_result_body(result: RatingResultRow) -> dict:
    return {
        "used_units": result.used_units,
        "quota_units": result.quota_units,
        "rollover_units": result.rollover_units,
        "billable_units": result.billable_units,
        "overage_amount": f"{result.overage_amount:.2f}",
    }


@app.get("/api/tenants/{tenant_id}/usage-rating")
def get_usage_rating(
    tenant_id: Annotated[UUID, Path()],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> dict:
    try:
        with connect() as connection:
            rating = rate_usage(
                PostgresRatingRepository(connection), tenant_id, period_start, period_end
            )
    except NoSubscriptionError as error:
        raise HTTPException(status_code=404, detail=NO_SUBSCRIPTION) from error
    return _usage_rating_body(rating)


@app.get("/api/tenants/{tenant_id}/usage-summary")
def get_usage_summary(
    tenant_id: Annotated[UUID, Path()],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> list[dict]:
    with connect() as connection:
        events = PostgresRatingRepository(connection).list_usage_events(tenant_id)
    return [
        {"kind": row.kind, "event_count": row.event_count, "units": row.units}
        for row in usage_summary(events, period_start, period_end)
    ]


@app.post("/api/tenants/{tenant_id}/rating-finalizations")
def finalize_tenant_rating(tenant_id: Annotated[UUID, Path()], request: RatingFinalization) -> dict:
    if request.period_end < request.period_start:
        raise HTTPException(status_code=422, detail="period_end must not precede period_start")
    try:
        with connect() as connection:
            results = finalize_rating(
                PostgresRatingRepository(connection),
                tenant_id,
                request.period_start,
                request.period_end,
            )
    except NoSubscriptionError as error:
        raise HTTPException(status_code=404, detail=NO_SUBSCRIPTION) from error
    except psycopg.errors.ForeignKeyViolation as error:
        raise HTTPException(
            status_code=409,
            detail="rating period id does not match the existing period",
        ) from error
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(
            status_code=409,
            detail="the rating period is being finalized concurrently; retry",
        ) from error
    rows = [_rating_result_body(item) for item in results]
    return {**rows[0], "rating_result": rows}


def _preview_line_body(line: InvoicePreviewLine) -> dict:
    return {
        "line_no": line.line_no,
        "line_type": line.line_type,
        "description": line.description,
        "amount": str(line.amount),
        "tax_amount": str(line.tax_amount),
        "credit_applied": str(line.credit_applied),
        "total": str(line.total),
    }


def _invoice_state_body(invoice: InvoiceRow) -> dict:
    return {
        "status": invoice.status,
        "subtotal": f"{invoice.subtotal:.2f}",
        "tax": f"{invoice.tax:.2f}",
        "total": f"{invoice.total:.2f}",
    }


def _credit_note_body(note: CreditNoteRow) -> dict:
    return {
        "credit_id": str(note.credit_id),
        "issued_on": note.issued_on.isoformat(),
        "amount": f"{note.amount:.2f}",
        "remaining_amount": f"{note.remaining_amount:.2f}",
    }


@app.get("/api/tenants/{tenant_id}/invoice-preview")
def get_invoice_preview(
    tenant_id: Annotated[UUID, Path()],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> list[dict]:
    try:
        with connect() as connection:
            lines = invoice_preview(
                PostgresInvoicingRepository(connection), tenant_id, period_start, period_end
            )
    except NoSubscriptionError as error:
        raise HTTPException(status_code=404, detail=NO_SUBSCRIPTION) from error
    return [_preview_line_body(line) for line in lines]


@app.post("/api/tenants/{tenant_id}/invoices")
def issue_tenant_invoice(tenant_id: Annotated[UUID, Path()], request: InvoiceIssue) -> dict:
    if request.period_end < request.period_start:
        raise HTTPException(status_code=422, detail="period_end must not precede period_start")
    try:
        with connect() as connection:
            issued = issue_invoice(
                PostgresInvoicingRepository(connection),
                tenant_id,
                request.period_start,
                request.period_end,
            )
    except NoSubscriptionError as error:
        raise HTTPException(status_code=404, detail=NO_SUBSCRIPTION) from error
    except NegativeInvoiceTotalError as error:
        raise HTTPException(
            status_code=409,
            detail="the invoice total would be negative after applying credit",
        ) from error
    except psycopg.errors.ForeignKeyViolation as error:
        raise HTTPException(
            status_code=409,
            detail="rating period id does not match the existing period",
        ) from error
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(
            status_code=409,
            detail="the invoice is being issued concurrently; retry",
        ) from error
    return {
        "invoice_id": str(issued.invoice.invoice_id),
        "period_id": str(issued.invoice.period_id),
        "issued_at": issued.invoice.issued_at.isoformat(),
        **_invoice_state_body(issued.invoice),
        "invoice_state": [_invoice_state_body(item) for item in issued.period_invoices],
        "credit_notes": [_credit_note_body(item) for item in issued.credit_notes],
    }


@app.get("/api/invoices/{invoice_id}/lines")
def get_invoice_lines(invoice_id: Annotated[UUID, Path()]) -> list[dict]:
    with connect() as connection:
        rows = PostgresInvoicingRepository(connection).list_invoice_lines(invoice_id)
    return [
        {
            "line_no": row.line_no,
            "line_type": row.line_type,
            "description": row.description,
            "amount": f"{row.amount:.2f}",
        }
        for row in invoice_lines(rows)
    ]
