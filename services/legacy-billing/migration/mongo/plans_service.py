#!/usr/bin/env python3
"""Unit u-08-plsql-plans: PKG_PLANS ported to the MongoDB service model.

Mirrors services/legacy-billing/db/oracle/packages/02_pkg_plans.sql against
the migrated collections `plans`, `tenants`, `subscriptions`,
`subscriptionsHist`, `billingAuditLog`:

- fn_list_plans  -> list_plans()
- fn_entitlement -> entitlement(): latest covering subscription wins
  (ORDER BY s.starts_on DESC, ROWNUM <= 1)
- sp_change_plan -> change_plan(): closes open subs (ends_on = eff - 1,
  cancelled stays cancelled = TRG_SUB_NO_UNCANCEL) then inserts a new sub
  with status 10; every subscription UPDATE/DELETE writes a full-row copy
  into `subscriptionsHist` (= TRG_SUBSCRIPTIONS_HIST) and the call logs to
  `billingAuditLog` (= pkg_ow_util.log_msg).
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

import ow_util

STATUS_ACTIVE = 10
STATUS_SUSPENDED = 20
STATUS_CANCELLED = 30

_STATUS_TEXT = {10: "active", 20: "suspended", 30: "cancelled"}
_TIER_TEXT = {1: "starter", 2: "growth", 3: "scale"}


def tier_text(tier_cd) -> str:
    return _TIER_TEXT.get(tier_cd, "UNKNOWN")


def status_text(status_cd) -> str:
    return _STATUS_TEXT.get(status_cd, "UNKNOWN")


def _utc(d: _dt.date) -> _dt.datetime:
    return _dt.datetime(d.year, d.month, d.day, tzinfo=_dt.timezone.utc)


def list_plans(db) -> list[dict[str, Any]]:
    """pkg_plans.fn_list_plans: active plans ordered by monthly_fee, code."""
    docs = db["plans"].find({"active": True}).sort(
        [("monthlyFee", 1), ("code", 1)]
    )
    return [
        {
            "plan_id": str(d["_id"]),
            "code": d.get("code"),
            "tier": tier_text(d.get("tierCd")),
            "monthly_fee": ow_util.dec2(d.get("monthlyFee")),
            "included_units": ow_util.json_value(d.get("includedUnits")),
            "overage_rate": ow_util.dec2(d.get("overageRate")),
        }
        for d in docs
    ]


def _latest_covering_sub(db, tenant_id: str, start: _dt.date, end: _dt.date):
    """Latest subscription covering [start, end] (startsOn DESC, limit 1)."""
    return db["subscriptions"].find_one(
        {
            "tenantId": tenant_id,
            "startsOn": {"$lte": _utc(end)},
            "$or": [{"endsOn": None}, {"endsOn": {"$gte": _utc(start)}}],
        },
        sort=[("startsOn", -1)],
    )


def entitlement(db, tenant_id: str, on: _dt.date) -> list[dict[str, Any]]:
    """pkg_plans.fn_entitlement: one row, latest covering subscription wins."""
    sub = _latest_covering_sub(db, tenant_id, on, on)
    if sub is None:
        return []
    plan = db["plans"].find_one({"_id": sub.get("planId")})
    return [
        {
            "tenant_id": tenant_id,
            "plan_code": plan.get("code") if plan else None,
            "tier": tier_text(plan.get("tierCd") if plan else None),
            "monthly_fee": ow_util.json_value(plan.get("monthlyFee")) if plan else None,
            "included_units": ow_util.json_value(plan.get("includedUnits"))
            if plan
            else None,
            "subscription_status": status_text(sub.get("statusCd")),
            # GREATEST(s.starts_on, p_on)
            "effective_on": max(sub["startsOn"].date(), on).isoformat()
            if sub.get("startsOn")
            else on.isoformat(),
        }
    ]


def _write_hist(db, old: dict, op: str) -> None:
    """TRG_SUBSCRIPTIONS_HIST equivalent: full-row copy of the OLD document."""
    coll = db["subscriptionsHist"]
    top = coll.find_one(sort=[("_id", -1)], projection={"_id": 1})
    hist_id = int(top["_id"]) + 1 if top else 1
    doc = {
        "_id": hist_id,
        "histDt": _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None),
        "histOp": op,
        "id": old["_id"],
        "tenantId": old.get("tenantId"),
        "planId": old.get("planId"),
        "startsOn": old.get("startsOn"),
        "endsOn": old.get("endsOn"),
        "statusCd": old.get("statusCd"),
        "suspendedOn": old.get("suspendedOn"),
    }
    coll.insert_one({k: v for k, v in doc.items() if v is not None or k == "_id"})


def change_plan(db, tenant_id: str, plan_id: str, effective_on: _dt.date) -> None:
    """pkg_plans.sp_change_plan + TRG_SUB_NO_UNCANCEL + TRG_SUBSCRIPTIONS_HIST."""
    ow_util.log_msg(
        db,
        "PLANS",
        f"sp_change_plan tenant={tenant_id} plan={plan_id} eff={effective_on.isoformat()}",
    )

    # Cursor-loop close-out of open subscriptions (ends_on IS NULL,
    # starts_on < effective). DECODE(status,30,30,10) IS the
    # TRG_SUB_NO_UNCANCEL invariant: cancelled can never leave cancelled.
    eff_dt = _utc(effective_on)
    close_to = eff_dt - _dt.timedelta(days=1)
    open_subs = db["subscriptions"].find(
        {
            "tenantId": tenant_id,
            "endsOn": None,
            "startsOn": {"$lt": eff_dt},
        }
    )
    for sub in open_subs:
        old_status = sub.get("statusCd")
        new_status = STATUS_CANCELLED if old_status == STATUS_CANCELLED else STATUS_ACTIVE
        db["subscriptions"].update_one(
            {"_id": sub["_id"]},
            {"$set": {"endsOn": close_to, "statusCd": new_status}},
        )
        _write_hist(db, sub, "UPD")

    new_id = ow_util.md5_uuid(tenant_id + plan_id + effective_on.isoformat())
    db["subscriptions"].insert_one(
        {
            "_id": new_id,
            "tenantId": tenant_id,
            "planId": plan_id,
            "startsOn": eff_dt,
            "statusCd": STATUS_ACTIVE,
        }
    )
