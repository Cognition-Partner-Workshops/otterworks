from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Path, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.db import connect, migrate, reset
from app.domain import (
    catalog,
    change_plan,
    entitlement,
    next_attempt_date,
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


class DunningRequest(BaseModel):
    as_of: date


def _format_sent_at(sent_at: datetime) -> str:
    return sent_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@app.get("/api/dunning/overdue")
def list_overdue_accounts(as_of: Annotated[date, Query()]) -> list[dict]:
    with connect() as connection:
        accounts = overdue_accounts(
            PostgresDunningRepository(connection).list_invoices(), as_of
        )
    return [
        {
            "tenant_id": str(row.tenant_id),
            "invoice_id": str(row.invoice_id),
            "total": f"{row.total:.2f}",
            "days_overdue": row.days_overdue,
            "tenant_status": row.tenant_status,
        }
        for row in accounts
    ]


@app.post("/api/dunning/schedule")
def schedule_dunning_attempts(request: DunningRequest) -> dict:
    with connect() as connection:
        repository = PostgresDunningRepository(connection)
        scheduled = schedule_dunning(repository, request.as_of)
        attempts = repository.list_attempts()
    latest: dict[str, dict] = {}
    for attempt in attempts:
        latest[str(attempt.invoice_id)] = {
            "attempt_no": attempt.attempt_no,
            "scheduled_for": attempt.scheduled_for.isoformat(),
            "status": attempt.status,
        }
    return {
        "as_of": request.as_of.isoformat(),
        "scheduled_for": next_attempt_date(request.as_of).isoformat(),
        "scheduled": [
            {
                "invoice_id": str(attempt.invoice_id),
                "tenant_id": str(attempt.tenant_id),
                "attempt_no": attempt.attempt_no,
                "scheduled_for": attempt.scheduled_for.isoformat(),
                "status": attempt.status,
            }
            for attempt in scheduled
        ],
        "latest_attempts": latest,
        "attempts": [
            {
                "invoice_id": str(attempt.invoice_id),
                "attempt_no": attempt.attempt_no,
                "scheduled_for": attempt.scheduled_for.isoformat(),
                "status": attempt.status,
            }
            for attempt in attempts
        ],
    }


@app.post("/api/dunning/suspend")
def suspend_overdue_tenants(request: DunningRequest) -> dict:
    with connect() as connection:
        repository = PostgresDunningRepository(connection)
        suspended = suspend_overdue(repository, request.as_of)
        tenant_ids = sorted(
            {
                invoice.tenant_id
                for invoice in repository.list_invoices()
                if invoice.status == "overdue"
            }
        )
        tenants: dict[str, dict] = {}
        for tenant_id in tenant_ids:
            tenant = repository.get_tenant(tenant_id)
            tenants[str(tenant_id)] = {
                "status": tenant.status if tenant else None,
                "subscriptions": [
                    {
                        "subscription_id": str(subscription.subscription_id),
                        "status": subscription.status,
                        "suspended_on": (
                            subscription.suspended_on.isoformat()
                            if subscription.suspended_on
                            else None
                        ),
                    }
                    for subscription in repository.list_subscriptions(tenant_id)
                ],
                "suspension_notifications": [
                    {
                        "id": str(notification.notification_id),
                        "kind": notification.kind,
                        "sent_at": _format_sent_at(notification.sent_at),
                    }
                    for notification in repository.list_notifications(
                        tenant_id, "suspension"
                    )
                ],
            }
        notifications = repository.list_suspension_notifications()
    return {
        "as_of": request.as_of.isoformat(),
        "suspended_tenants": [str(tenant_id) for tenant_id in suspended],
        "tenants": tenants,
        "suspension_notifications": [
            {
                "id": str(notification.notification_id),
                "tenant_id": str(notification.tenant_id),
                "kind": notification.kind,
                "sent_at": _format_sent_at(notification.sent_at),
            }
            for notification in notifications
        ],
    }
