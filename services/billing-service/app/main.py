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
    RatingSubscriptionNotFound,
    catalog,
    change_plan,
    entitlement,
    finalize_rating,
    rate_tenant,
    usage_summary,
)
from app.repository import PostgresPlansRepository, PostgresRatingRepository


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


# --- rating ---
class RatingPeriod(BaseModel):
    period_start: date
    period_end: date


def _check_period(period_start: date, period_end: date) -> None:
    if period_end < period_start:
        raise HTTPException(status_code=400, detail="period_end precedes period_start")


@app.get("/api/tenants/{tenant_id}/rating")
def get_rating(
    tenant_id: Annotated[UUID, Path()],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> dict:
    _check_period(period_start, period_end)
    try:
        with connect() as connection:
            rating = rate_tenant(
                PostgresRatingRepository(connection),
                tenant_id,
                period_start,
                period_end,
            )
    except RatingSubscriptionNotFound as error:
        raise HTTPException(
            status_code=404, detail="no subscription overlaps the rating period"
        ) from error
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


@app.get("/api/tenants/{tenant_id}/usage-summary")
def get_usage_summary(
    tenant_id: Annotated[UUID, Path()],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> list[dict]:
    _check_period(period_start, period_end)
    with connect() as connection:
        events = PostgresRatingRepository(connection).list_usage_events(tenant_id)
    rows = usage_summary(events, period_start, period_end)
    return [
        {"kind": row.kind, "event_count": row.event_count, "units": row.units}
        for row in rows
    ]


@app.post("/api/tenants/{tenant_id}/rating/finalize")
def post_finalize_rating(
    tenant_id: Annotated[UUID, Path()],
    request: RatingPeriod,
) -> dict:
    _check_period(request.period_start, request.period_end)
    try:
        with connect() as connection:
            rows = finalize_rating(
                PostgresRatingRepository(connection),
                tenant_id,
                request.period_start,
                request.period_end,
            )
    except RatingSubscriptionNotFound as error:
        raise HTTPException(
            status_code=404, detail="no subscription overlaps the rating period"
        ) from error
    except psycopg.errors.ForeignKeyViolation as error:
        raise HTTPException(
            status_code=409, detail="rating result conflicts with an existing period"
        ) from error
    return {
        "tenant_id": str(tenant_id),
        "period_start": request.period_start.isoformat(),
        "period_end": request.period_end.isoformat(),
        "rating_results": [
            {
                "used_units": row.used_units,
                "quota_units": row.quota_units,
                "rollover_units": row.rollover_units,
                "billable_units": row.billable_units,
                "overage_amount": f"{row.overage_amount:.2f}",
            }
            for row in rows
        ],
    }
