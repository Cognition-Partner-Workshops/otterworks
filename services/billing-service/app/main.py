from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, HTTPException, Path, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.config import settings
from app.db import client, database, reset
from app.domain import (
    InvalidPeriodError,
    InvoiceLineRow,
    NoSubscriptionError,
    catalog,
    change_plan,
    entitlement,
    finalize_rating,
    invoice_lines,
    invoice_preview,
    issue_invoice,
    usage_rating,
    usage_summary,
)
from app.dunning import (
    NotificationRow,
    overdue_accounts,
    schedule_dunning,
    suspend_overdue,
)
from app.dunning_repository import MongoDunningRepository
from app.repository import (
    MissingReferenceError,
    MongoInvoicingRepository,
    MongoPlansRepository,
    MongoRatingRepository,
)

app = FastAPI(title=settings.app_name)
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


class RatingPeriod(BaseModel):
    period_start: date
    period_end: date


class DunningRun(BaseModel):
    as_of: date


def _line(line: InvoiceLineRow) -> dict:
    return {
        "line_id": str(line.line_id),
        "line_no": line.line_no,
        "line_type": line.line_type,
        "description": line.description,
        "amount": f"{line.amount:.2f}",
    }


def _notification(row: NotificationRow) -> dict:
    return {
        "id": str(row.notification_id),
        "tenant_id": str(row.tenant_id),
        "kind": row.kind,
        "sent_at": row.sent_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


@app.get("/health")
def health() -> dict[str, str]:
    try:
        client().admin.command("ping")
    except PyMongoError as error:
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
    plans = catalog(MongoPlansRepository(database()).list_plans())
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
    row = entitlement(
        MongoPlansRepository(database()).find_entitlements(tenant_id),
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
    repository = MongoPlansRepository(database())
    try:
        subscriptions, created = repository.run_in_transaction(
            lambda: change_plan(repository, tenant_id, request.plan_id, request.effective_on)
        )
    except MissingReferenceError as error:
        raise HTTPException(status_code=400, detail="invalid plan change") from error
    except DuplicateKeyError as error:
        raise HTTPException(
            status_code=409,
            detail="this plan change has already been requested",
        ) from error
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


@app.get("/api/tenants/{tenant_id}/rating")
def get_usage_rating(
    tenant_id: Annotated[UUID, Path()],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> dict:
    try:
        row = usage_rating(MongoRatingRepository(database()), tenant_id, period_start, period_end)
    except NoSubscriptionError as error:
        raise HTTPException(status_code=404, detail="no subscription in the period") from error
    return {
        "tenant_id": str(row.tenant_id),
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "used_units": row.used_units,
        "quota_units": row.quota_units,
        "rollover_units": row.rollover_units,
        "billable_units": row.billable_units,
        "first_tier_units": row.first_tier_units,
        "second_tier_units": row.second_tier_units,
        "overage_amount": f"{row.overage_amount:.2f}",
    }


@app.get("/api/tenants/{tenant_id}/usage-summary")
def get_usage_summary(
    tenant_id: Annotated[UUID, Path()],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> list[dict]:
    rows = usage_summary(MongoRatingRepository(database()), tenant_id, period_start, period_end)
    return [{"kind": row.kind, "event_count": row.event_count, "units": row.units} for row in rows]


@app.post("/api/tenants/{tenant_id}/rating-periods")
def finalize_tenant_rating(tenant_id: Annotated[UUID, Path()], request: RatingPeriod) -> dict:
    repository = MongoRatingRepository(database())
    try:
        result = repository.run_in_transaction(
            lambda: finalize_rating(repository, tenant_id, request.period_start, request.period_end)
        )
    except InvalidPeriodError as error:
        raise HTTPException(status_code=400, detail="period_end is before period_start") from error
    except NoSubscriptionError as error:
        raise HTTPException(status_code=404, detail="no subscription in the period") from error
    row = {
        "used_units": result.used_units,
        "quota_units": result.quota_units,
        "rollover_units": result.rollover_units,
        "billable_units": result.billable_units,
        "overage_amount": f"{result.overage_amount:.2f}",
    }
    return {
        "period_id": str(result.period_id),
        "result_id": str(result.result_id),
        "subscription_id": str(result.subscription_id),
        **row,
        "rating_result": [row],
    }


@app.get("/api/tenants/{tenant_id}/invoice-preview")
def preview_tenant_invoice(
    tenant_id: Annotated[UUID, Path()],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> list[dict]:
    try:
        lines = invoice_preview(
            MongoInvoicingRepository(database()), tenant_id, period_start, period_end
        )
    except NoSubscriptionError as error:
        raise HTTPException(status_code=404, detail="no subscription in the period") from error
    # amounts are the function's exact numerics (tax halves are not rounded to cents)
    return [
        {
            "line_no": line.line_no,
            "line_type": line.line_type,
            "description": line.description,
            "amount": f"{line.amount:f}",
            "tax_amount": f"{line.tax_amount:f}",
            "credit_applied": f"{line.credit_applied:f}",
            "total": f"{line.total:f}",
        }
        for line in lines
    ]


@app.post("/api/tenants/{tenant_id}/invoices")
def issue_tenant_invoice(tenant_id: Annotated[UUID, Path()], request: RatingPeriod) -> dict:
    repository = MongoInvoicingRepository(database())
    try:
        invoice, notes = repository.run_in_transaction(
            lambda: issue_invoice(repository, tenant_id, request.period_start, request.period_end)
        )
    except InvalidPeriodError as error:
        raise HTTPException(status_code=400, detail="period_end is before period_start") from error
    except NoSubscriptionError as error:
        raise HTTPException(status_code=404, detail="no subscription in the period") from error
    state = {
        "status": invoice.status,
        "subtotal": f"{invoice.subtotal:.2f}",
        "tax": f"{invoice.tax:.2f}",
        "total": f"{invoice.total:.2f}",
    }
    return {
        "invoice_id": str(invoice.invoice_id),
        "tenant_id": str(invoice.tenant_id),
        "period_id": str(invoice.period_id),
        "issued_at": invoice.issued_at.isoformat(),
        **state,
        "invoice_lines": [_line(line) for line in invoice.lines],
        "credit_notes": [
            {
                "id": str(note.note_id),
                "issued_on": note.issued_on.isoformat(),
                "amount": f"{note.amount:.2f}",
                "remaining_amount": f"{note.remaining_amount:.2f}",
            }
            for note in notes
        ],
        "invoice_state": [state],
    }


@app.get("/api/invoices/{invoice_id}/lines")
def get_invoice_lines(invoice_id: Annotated[UUID, Path()]) -> list[dict]:
    return [_line(line) for line in invoice_lines(MongoInvoicingRepository(database()), invoice_id)]


@app.get("/api/dunning/overdue-accounts")
def list_overdue_accounts(as_of: Annotated[date, Query()]) -> list[dict]:
    rows = overdue_accounts(MongoDunningRepository(database()), as_of)
    return [
        {
            "tenant_id": str(row.tenant_id),
            "invoice_id": str(row.invoice_id),
            "total": f"{row.total:.2f}",
            "days_overdue": row.days_overdue,
            "tenant_status": row.tenant_status,
        }
        for row in rows
    ]


@app.post("/api/dunning/schedule-runs")
def run_dunning_schedule(request: DunningRun) -> dict:
    repository = MongoDunningRepository(database())
    scheduled = repository.run_in_transaction(lambda: schedule_dunning(repository, request.as_of))
    return {
        "as_of": request.as_of.isoformat(),
        # the invoices sp_schedule_dunning walked, each with the attempt it holds afterwards
        "latest_attempts": {
            str(item.invoice.invoice_id): {
                "invoice_id": str(item.invoice.invoice_id),
                "tenant_id": str(item.invoice.tenant_id),
                "attempt_no": item.attempt.attempt_no,
                "scheduled_for": item.attempt.scheduled_for.isoformat(),
                "status": item.attempt.status,
                "appended": item.appended,
            }
            for item in scheduled
        },
        # every dunning attempt of every invoice, as the legacy dunning_attempts table reads
        "attempts": [
            {
                "invoice_id": str(invoice_id),
                "attempt_no": attempt.attempt_no,
                "scheduled_for": attempt.scheduled_for.isoformat(),
                "status": attempt.status,
            }
            for invoice_id, attempt in repository.list_dunning_attempts()
        ],
    }


@app.post("/api/dunning/suspension-runs")
def run_overdue_suspension(request: DunningRun) -> dict:
    repository = MongoDunningRepository(database())
    rows = repository.run_in_transaction(lambda: suspend_overdue(repository, request.as_of))
    return {
        "as_of": request.as_of.isoformat(),
        # the tenants sp_suspend_overdue evaluated (an overdue invoice past the grace period)
        "tenants": {
            str(row.tenant_id): {
                "tenant_id": str(row.tenant_id),
                "tenant_status": row.tenant_status,
                "suspended_now": row.suspended_now,
                "subscriptions": [
                    {
                        "subscription_id": str(item.subscription_id),
                        "plan_id": str(item.plan_id),
                        "status": item.status,
                        "suspended_on": (
                            item.suspended_on.isoformat() if item.suspended_on else None
                        ),
                    }
                    for item in row.subscriptions
                ],
                "notification_kinds": [item.kind for item in row.notifications],
            }
            for row in rows
        },
        "suspension_notifications": [
            _notification(row) for row in repository.list_notifications("suspension")
        ],
    }
