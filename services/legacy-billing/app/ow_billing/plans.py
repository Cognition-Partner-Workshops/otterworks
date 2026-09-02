"""Application-side equivalents of PKG_PLANS."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from bson import Decimal128, Int64
from pymongo import ReturnDocument

from . import NS_VALUE
from . import util

TIER = {1: "starter", 2: "growth", 3: "scale"}
SUB_STATUS = {10: "active", 20: "suspended", 30: "cancelled"}
UNKNOWN = "UNKNOWN"


def decode(mapping: dict[int, str], value: int | None) -> str:
    return mapping.get(value, UNKNOWN)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))


def fn_list_plans(store) -> list[dict]:
    util.log_msg(store, "PLANS", "fn_list_plans")
    rows = store.coll("plans").aggregate(
        [
            {"$match": {"active_yn": "Y"}},
            {"$sort": {"monthly_fee": 1, "code": 1}},
            {
                "$project": {
                    "_id": 0,
                    "id": 1,
                    "code": 1,
                    "tier_cd": 1,
                    "monthly_fee": 1,
                    "included_units": 1,
                    "overage_rate": 1,
                }
            },
        ]
    )
    return [
        {
            "plan_id": row.get("id", row.get("_id")),
            "code": row.get("code"),
            "tier": decode(TIER, row.get("tier_cd")),
            "monthly_fee": _decimal(row.get("monthly_fee")),
            "included_units": int(row["included_units"]),
            "overage_rate": _decimal(row.get("overage_rate")),
        }
        for row in rows
    ]


def fn_entitlement(store, tenant_id: str, on: date) -> dict | None:
    on_dt = datetime(on.year, on.month, on.day)
    tenant_collection = store.coll("tenants").name
    plan_collection = store.coll("plans").name
    rows = store.coll("subscriptions").aggregate(
        [
            {
                "$match": {
                    "tenant_id": tenant_id,
                    "starts_on": {"$lte": on_dt},
                    "$or": [{"ends_on": None}, {"ends_on": {"$gte": on_dt}}],
                }
            },
            {
                "$lookup": {
                    "from": tenant_collection,
                    "localField": "tenant_id",
                    "foreignField": "_id",
                    "as": "tenant",
                }
            },
            {"$match": {"tenant.0": {"$exists": True}}},
            {
                "$lookup": {
                    "from": plan_collection,
                    "localField": "plan_id",
                    "foreignField": "_id",
                    "as": "plan",
                }
            },
            {"$sort": {"starts_on": -1}},
            {"$limit": 1},
        ]
    )
    row = next(iter(rows), None)
    if row is None:
        return None
    plan = next(iter(row.get("plan") or []), None)
    starts_on = row["starts_on"]
    starts_date = starts_on.date() if isinstance(starts_on, datetime) else starts_on
    return {
        "tenant_id": row.get("tenant_id", tenant_id),
        "plan_code": plan.get("code") if plan else None,
        "tier": decode(TIER, plan.get("tier_cd") if plan else None),
        "monthly_fee": _decimal(plan.get("monthly_fee")) if plan else None,
        "included_units": int(plan["included_units"]) if plan else None,
        "subscription_status": decode(SUB_STATUS, row.get("status_cd")),
        "effective_on": max(starts_date, on),
    }


def _next_value(store, sequence: str, session) -> Int64:
    doc = store.coll("counters").find_one_and_update(
        {"_id": sequence},
        {"$inc": {"seq": Int64(1)}},
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    if doc is None:
        raise LookupError(f"counter {sequence!r} is not seeded")
    return Int64(doc["seq"])


def subscriptions_for_tenant(store, tenant_id: str) -> list[dict]:
    rows = store.coll("subscriptions").find({"tenant_id": tenant_id}).sort(
        [("starts_on", 1), ("_id", 1)]
    )
    result = []
    for row in rows:
        starts_on = row["starts_on"]
        ends_on = row.get("ends_on")
        result.append(
            {
                "plan_id": row.get("plan_id"),
                "starts_on": starts_on.date() if isinstance(starts_on, datetime) else starts_on,
                "ends_on": ends_on.date() if isinstance(ends_on, datetime) else ends_on,
                "status": decode(SUB_STATUS, row.get("status_cd")),
            }
        )
    return result


def sp_change_plan(
    store, tenant_id: str, plan_id: str, effective_on: date
) -> list[dict]:
    util.log_msg(
        store,
        "PLANS",
        f"sp_change_plan tenant={tenant_id} plan={plan_id} "
        f"eff={effective_on.isoformat()}",
    )
    eff = datetime(effective_on.year, effective_on.month, effective_on.day)

    def txn(session):
        if (
            store.coll("tenants").find_one({"_id": tenant_id}, session=session) is None
            or store.coll("plans").find_one({"_id": plan_id}, session=session) is None
        ):
            raise LookupError("plan change references an unknown tenant or plan")
        open_subscriptions = list(
            store.coll("subscriptions")
            .find(
                {
                    "tenant_id": tenant_id,
                    "ends_on": None,
                    "starts_on": {"$lt": eff},
                },
                session=session,
            )
            .sort("_id", 1)
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for prior in open_subscriptions:
            new_status = 30 if prior["status_cd"] == 30 else 10
            updated = store.coll("subscriptions").find_one_and_update(
                {"_id": prior["_id"], "ends_on": None},
                {
                    "$set": {
                        "ends_on": eff - timedelta(days=1),
                        "status_cd": new_status,
                    }
                },
                return_document=ReturnDocument.BEFORE,
                session=session,
            )
            if updated is None:
                raise RuntimeError("subscription changed concurrently")
            hist_id = _next_value(store, util.SEQ_SUBSCRIPTIONS_HIST, session)
            history = {
                "_id": hist_id,
                "hist_id": hist_id,
                "hist_dt": f"{util.f_dt2str(now)} {now:%H:%M:%S}",
                "hist_op": "UPD",
                "id": prior.get("id", prior.get("_id")),
                "tenant_id": prior.get("tenant_id"),
                "plan_id": prior.get("plan_id"),
                "starts_on": prior.get("starts_on"),
                "ends_on": prior.get("ends_on"),
                "status_cd": prior.get("status_cd"),
                "suspended_on": prior.get("suspended_on"),
                "ns": NS_VALUE,
            }
            store.coll("subscriptions_history").insert_one(history, session=session)
        new_id = util.f_md5_uuid(
            f"{tenant_id}{plan_id}{effective_on.isoformat()}"
        )
        store.coll("subscriptions").insert_one(
            {
                "_id": new_id,
                "id": new_id,
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "starts_on": eff,
                "ends_on": None,
                "status_cd": 10,
                "suspended_on": None,
                "ns": NS_VALUE,
            },
            session=session,
        )

    with store.client.start_session() as session:
        session.with_transaction(txn)
    return subscriptions_for_tenant(store, tenant_id)
