"""MongoDB-backed billing plan entrypoints and HTTP routes."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from typing import Any

from flask import Blueprint, jsonify, request

from . import TARGET_DB, Store, mongo_client
from . import dunning
from . import plans

plans_api = Blueprint("plans_api", __name__)


def _money(value: Decimal | None, places: int) -> str | None:
    return None if value is None else f"{value:.{places}f}"


def call_entrypoint(store, name: str, inputs: dict) -> Any:
    if name == "billing.fn_list_plans":
        return [
            {
                "plan_id": row["plan_id"],
                "code": row["code"],
                "tier": row["tier"],
                "monthly_fee": _money(row["monthly_fee"], 2),
                "included_units": int(row["included_units"]),
                "overage_rate": _money(row["overage_rate"], 6),
            }
            for row in plans.fn_list_plans(store)
        ]
    if name == "billing.fn_entitlement":
        row = plans.fn_entitlement(
            store, inputs["tenant_id"], date.fromisoformat(inputs["as_of"])
        )
        if row is None:
            return None
        return {
            "tenant_id": row["tenant_id"],
            "plan_code": row["plan_code"],
            "tier": row["tier"],
            "monthly_fee": _money(row["monthly_fee"], 2),
            "included_units": row["included_units"],
            "subscription_status": row["subscription_status"],
            "effective_on": row["effective_on"].isoformat(),
        }
    if name == "billing.sp_change_plan":
        rows = plans.sp_change_plan(
            store,
            inputs["tenant_id"],
            inputs["plan_id"],
            date.fromisoformat(inputs["effective_on"]),
        )
        return {
            "latest_plan": rows[-1]["plan_id"],
            "latest_start": rows[-1]["starts_on"].isoformat(),
            "subscriptions": [
                {
                    "plan_id": row["plan_id"],
                    "starts_on": row["starts_on"].isoformat(),
                    "ends_on": row["ends_on"].isoformat() if row["ends_on"] else None,
                    "status": row["status"],
                }
                for row in rows
            ],
        }
    if name == "billing.fn_overdue_accounts":
        return [
            {
                "tenant_id": row["tenant_id"],
                "invoice_id": row["invoice_id"],
                "total": _money(row["total"], 2),
                "days_overdue": int(row["days_overdue"]),
                "tenant_status": row["tenant_status"],
            }
            for row in dunning.fn_overdue_accounts(
                store, date.fromisoformat(inputs["as_of"])
            )
        ]
    if name == "billing.sp_schedule_dunning":
        return {
            "status": "scheduled",
            "scheduled": dunning.sp_schedule_dunning(
                store, date.fromisoformat(inputs["as_of"])
            ),
        }
    if name == "billing.sp_suspend_overdue":
        return {
            "status": "suspended",
            "tenant_ids": dunning.sp_suspend_overdue(
                store, date.fromisoformat(inputs["as_of"])
            ),
        }
    raise KeyError(f"unknown billing entrypoint: {name}")


ENTRYPOINTS = {
    "billing.fn_list_plans": plans.fn_list_plans,
    "billing.fn_entitlement": plans.fn_entitlement,
    "billing.sp_change_plan": plans.sp_change_plan,
    "billing.fn_overdue_accounts": dunning.fn_overdue_accounts,
    "billing.sp_schedule_dunning": dunning.sp_schedule_dunning,
    "billing.sp_suspend_overdue": dunning.sp_suspend_overdue,
}


def _store() -> Store:
    return Store(
        mongo_client(),
        os.getenv("MONGODB_DB", TARGET_DB),
        os.getenv("OW_BILLING_COLLECTION_PREFIX", ""),
    )


@plans_api.get("/api/plans")
def list_plans():
    return jsonify(call_entrypoint(_store(), "billing.fn_list_plans", {}))


@plans_api.get("/api/tenants/<tenant_id>/entitlement")
def entitlement(tenant_id):
    row = call_entrypoint(
        _store(),
        "billing.fn_entitlement",
        {"tenant_id": tenant_id, "as_of": request.args.get("on", "2026-02-28")},
    )
    if row is None:
        return jsonify(detail="entitlement not found"), 404
    return jsonify(row)


@plans_api.post("/api/tenants/<tenant_id>/plan-change")
def change_plan(tenant_id):
    payload = request.get_json(force=True)
    try:
        row = call_entrypoint(
            _store(),
            "billing.sp_change_plan",
            {
                "tenant_id": tenant_id,
                "plan_id": payload["plan_id"],
                "effective_on": payload["effective_on"],
            },
        )
    except (KeyError, LookupError, ValueError, TypeError):
        return jsonify(detail="invalid plan change"), 400
    return jsonify(row)


def _as_of_payload() -> str:
    payload = request.get_json(silent=True) or request.form
    return payload.get("as_of", "2026-02-28")


@plans_api.get("/api/dunning/overdue")
def overdue_accounts():
    return jsonify(
        call_entrypoint(
            _store(),
            "billing.fn_overdue_accounts",
            {"as_of": request.args.get("as_of", "2026-02-28")},
        )
    )


@plans_api.post("/api/dunning/schedule")
def schedule_dunning():
    return jsonify(
        call_entrypoint(
            _store(),
            "billing.sp_schedule_dunning",
            {"as_of": _as_of_payload()},
        )
    )


@plans_api.post("/api/dunning/suspend")
def suspend_overdue():
    return jsonify(
        call_entrypoint(
            _store(),
            "billing.sp_suspend_overdue",
            {"as_of": _as_of_payload()},
        )
    )
