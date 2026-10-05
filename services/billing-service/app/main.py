from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Path, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.db import connect, migrate, reset
from app.domain import (
    DunningAttemptRow,
    catalog,
    change_plan,
    dunning_schedule_date,
    entitlement,
    overdue_accounts,
    schedule_dunning,
    suspend_overdue,
)
from app.repository import PostgresDunningRepository, PostgresPlansRepository


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


# --- dunning ---


class DunningRequest(BaseModel):
    as_of: date


def _attempt_response(attempt: DunningAttemptRow) -> dict:
    return {
        "invoice_id": str(attempt.invoice_id),
        "attempt_no": attempt.attempt_no,
        "scheduled_for": attempt.scheduled_for.isoformat(),
        "status": attempt.status,
    }


@app.get("/api/dunning/overdue")
def list_overdue_accounts(as_of: Annotated[date, Query()]) -> list[dict]:
    with connect() as connection:
        rows = overdue_accounts(
            PostgresDunningRepository(connection).list_dunning_invoices(),
            as_of,
        )
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


@app.post("/api/dunning/schedule")
def schedule_overdue_dunning(request: DunningRequest) -> dict:
    with connect() as connection:
        repository = PostgresDunningRepository(connection)
        created = schedule_dunning(repository, request.as_of)
        attempts = repository.list_dunning_attempts()
    latest = (
        max(enumerate(created), key=lambda item: (item[1].attempt_no, item[0]))[1]
        if created
        else None
    )
    return {
        "as_of": request.as_of.isoformat(),
        "scheduled_for": dunning_schedule_date(request.as_of).isoformat(),
        "created": [_attempt_response(attempt) for attempt in created],
        "latest_attempt": _attempt_response(latest) if latest is not None else None,
        "schedule_rows": [_attempt_response(attempt) for attempt in attempts],
    }


@app.post("/api/dunning/suspend")
def suspend_overdue_accounts(request: DunningRequest) -> dict:
    with connect() as connection:
        repository = PostgresDunningRepository(connection)
        subscriptions = suspend_overdue(repository, request.as_of)
        notifications = repository.list_suspension_notifications()
    rows = [
        {
            "tenant_id": str(row.tenant_id),
            "subscription_id": str(row.subscription_id),
            "status": row.status,
            "suspended_on": row.suspended_on.isoformat() if row.suspended_on else None,
        }
        for row in subscriptions
    ]
    notification_rows = [
        {
            "id": str(row.notification_id),
            "tenant_id": str(row.tenant_id),
            "kind": row.kind,
            "sent_at": row.sent_at.astimezone(UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
        }
        for row in notifications
    ]
    return {
        "as_of": request.as_of.isoformat(),
        "suspended_subscriptions": rows,
        "latest_suspension": rows[-1] if rows else None,
        "suspension_notifications": notification_rows,
    }
