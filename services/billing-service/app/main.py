from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Path, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.db import connect, migrate, reset
from app.domain import (
    InvoicingError,
    catalog,
    change_plan,
    entitlement,
    invoice_preview,
    issue_invoice,
)
from app.repository import PostgresInvoicingRepository, PostgresPlansRepository


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


# --- invoicing ----------------------------------------------------------------


class InvoiceIssue(BaseModel):
    period_start: date
    period_end: date


def _invoicing_decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _invoice_state_row(row: dict) -> dict:
    return {
        "status": row["status"],
        "subtotal": str(row["subtotal"]),
        "tax": str(row["tax"]),
        "total": str(row["total"]),
    }


@app.get("/api/invoices/{tenant_id}/preview")
def get_invoice_preview(
    tenant_id: Annotated[UUID, Path()],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> list[dict]:
    with connect() as connection:
        lines = invoice_preview(
            PostgresInvoicingRepository(connection), tenant_id, period_start, period_end
        )
    return [
        {
            "line_no": line.line_no,
            "line_type": line.line_type,
            "description": line.description,
            "amount": _invoicing_decimal(line.amount),
            "tax_amount": _invoicing_decimal(line.tax_amount),
            "credit_applied": _invoicing_decimal(line.credit_applied),
            "total": _invoicing_decimal(line.total),
        }
        for line in lines
    ]


@app.post("/api/invoices/{tenant_id}/issue")
def issue_tenant_invoice(tenant_id: Annotated[UUID, Path()], request: InvoiceIssue) -> dict:
    try:
        with connect() as connection:
            repository = PostgresInvoicingRepository(connection)
            invoice_id, period_id = issue_invoice(
                repository, tenant_id, request.period_start, request.period_end
            )
            state = [_invoice_state_row(row) for row in repository.invoice_state(period_id)]
            credit_notes = repository.list_credit_notes(tenant_id)
    except InvoicingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except psycopg.errors.IntegrityError as error:
        raise HTTPException(status_code=409, detail="invoice could not be issued") from error
    return {
        "invoice_id": str(invoice_id),
        "period_id": str(period_id),
        "invoice": state[0] if state else None,
        "invoice_state": state,
        "credit_notes": [
            {
                "id": str(row["id"]),
                "issued_on": row["issued_on"].isoformat(),
                "remaining_amount": str(row["remaining_amount"]),
            }
            for row in credit_notes
        ],
    }


@app.get("/api/invoices/{invoice_id}/lines")
def get_invoice_lines(invoice_id: Annotated[UUID, Path()]) -> list[dict]:
    with connect() as connection:
        lines = PostgresInvoicingRepository(connection).list_invoice_lines(invoice_id)
    return [
        {
            "line_no": line.line_no,
            "line_type": line.line_type,
            "description": line.description,
            "amount": str(line.amount),
        }
        for line in lines
    ]
