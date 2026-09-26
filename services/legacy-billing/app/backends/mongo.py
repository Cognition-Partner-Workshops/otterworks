"""MongoDB backend for the tenancy read paths (unit u-01-tenancy).

Covers `pkg_plans.fn_list_plans`, `pkg_plans.fn_entitlement` and the `/me` tenant lookup
against `ow_billing_migration` (tenants, plans, subscriptions; `codes` is read as reference
data owned by another unit). Row shapes match `backends.oracle` so the facade serializes both
identically. Writes (ensure_tenant, change_plan) stay on the Oracle package.
Selected per request through facade._tenancy() (TENANCY_BACKEND=mongo).
"""

import os
from datetime import date, datetime, time
from decimal import Decimal

from bson.decimal128 import Decimal128
from pymongo import DESCENDING, MongoClient

NAME = "mongo"

TIER_NAMES = {1: "starter", 2: "growth", 3: "scale"}
SUBSCRIPTION_STATUS = {10: "active", 20: "suspended", 30: "cancelled"}

_client = None


def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGO_BILLING_URI"])
    return _client[os.getenv("MONGO_BILLING_DB", "ow_billing_migration")]


def _number(value):
    """Oracle NUMBER round-trips as a Decimal string without stored scale ("49", not "49.00")."""
    return f"{Decimal(value).normalize():f}"


def _json_value(value):
    if isinstance(value, Decimal128):
        return _number(value.to_decimal())
    if isinstance(value, (Decimal, int)) and not isinstance(value, bool):
        return _number(value)
    if isinstance(value, datetime):
        if value.time() == time.min:
            return value.date().isoformat()
        return value.isoformat()
    return value


def _row(**fields):
    return {name: _json_value(value) for name, value in fields.items()}


def _as_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return datetime.combine(date.fromisoformat(str(value)), time.min)


def health():
    _db().command("ping")


def list_plans():
    cursor = _db().plans.find({"active": True}).sort([("monthlyFee", 1), ("code", 1)])
    return [
        _row(
            plan_id=plan["_id"],
            code=plan.get("code"),
            tier=TIER_NAMES.get(plan.get("tierCd"), "UNKNOWN"),
            monthly_fee=plan.get("monthlyFee"),
            included_units=plan.get("includedUnits"),
            overage_rate=plan.get("overageRate"),
        )
        for plan in cursor
    ]


def _covering_subscription(tenant_id, on):
    """Latest subscription covering `on`; mirrors the (+) join and ORDER BY starts_on DESC."""
    return _db().subscriptions.find_one(
        {
            "tenantId": tenant_id,
            "startsOn": {"$lte": on},
            "$or": [{"endsOn": {"$exists": False}}, {"endsOn": None}, {"endsOn": {"$gte": on}}],
        },
        sort=[("startsOn", DESCENDING)],
    )


def entitlement(tenant_id, on):
    on = _as_datetime(on)
    db = _db()
    if db.tenants.find_one({"_id": tenant_id}, {"_id": 1}) is None:
        return []
    subscription = _covering_subscription(tenant_id, on)
    if subscription is None:
        return []
    plan = db.plans.find_one({"_id": subscription.get("planId")}) or {}
    return [
        _row(
            tenant_id=tenant_id,
            plan_code=plan.get("code"),
            tier=TIER_NAMES.get(plan.get("tierCd"), "UNKNOWN"),
            monthly_fee=plan.get("monthlyFee"),
            included_units=plan.get("includedUnits"),
            subscription_status=SUBSCRIPTION_STATUS.get(subscription.get("statusCd"), "UNKNOWN"),
            effective_on=max(subscription["startsOn"], on),
        )
    ]


def tenant_profile(tenant_id):
    """The `/me` tenant row: tenants LEFT JOIN codes (TENANT_STATUS) on status_cd."""
    db = _db()
    pipeline = [
        {"$match": {"_id": tenant_id}},
        {
            "$lookup": {
                "from": "codes",
                "let": {"status": "$statusCd"},
                "pipeline": [
                    {"$match": {"$expr": {"$and": [
                        {"$eq": ["$codeType", "TENANT_STATUS"]},
                        {"$eq": ["$codeVal", "$$status"]},
                    ]}}},
                    {"$limit": 1},
                ],
                "as": "status",
            }
        },
    ]
    return [
        _row(
            tenant_id=tenant["_id"],
            name=tenant.get("name"),
            status=(tenant["status"][0].get("codeDesc") if tenant.get("status") else None),
            tax_exempt="Y" if tenant.get("taxExempt") else "N",
        )
        for tenant in db.tenants.aggregate(pipeline)
    ]
