from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated
from uuid import UUID

import jwt
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.db import connect, migrate, reset
from app.domain import catalog, change_plan, entitlement
from app.repository import PostgresPlansRepository


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


def require_tenant(
    tenant_id: UUID,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    try:
        secret = os.environ.get("JWT_SECRET", "")
        if not secret or not authorization or not authorization.startswith("Bearer "):
            raise jwt.InvalidTokenError()
        claims = jwt.decode(
            authorization[7:],
            secret,
            algorithms=["HS256", "HS384"],
            options={"require": ["sub", "exp"]},
        )
        if not claims["sub"] or claims.get("type") != "access":
            raise jwt.InvalidTokenError()
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="Authentication required") from error
    roles = claims.get("roles", [])
    tenants = claims.get("tenant_ids", [])
    if (isinstance(roles, list) and "ADMIN" in roles) or claims.get("tenant_id") == str(tenant_id):
        return
    if isinstance(tenants, list) and str(tenant_id) in tenants:
        return
    try:
        user_id = UUID(claims["sub"])
    except (ValueError, TypeError, AttributeError) as error:
        raise HTTPException(status_code=403, detail="Tenant access denied") from error
    with connect() as connection:
        if PostgresPlansRepository(connection).is_tenant_member(tenant_id, user_id):
            return
    raise HTTPException(status_code=403, detail="Tenant access denied")


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


@app.get("/api/tenants/{tenant_id}/entitlement", dependencies=[Depends(require_tenant)])
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


@app.post("/api/tenants/{tenant_id}/plan-change", dependencies=[Depends(require_tenant)])
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
