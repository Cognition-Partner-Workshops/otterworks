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
from app.domain import catalog, change_plan, entitlement
from app.repository import MissingReferenceError, MongoPlansRepository

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
        with repository.transaction():
            subscriptions, created = change_plan(
                repository,
                tenant_id,
                request.plan_id,
                request.effective_on,
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
