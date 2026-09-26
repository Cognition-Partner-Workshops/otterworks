#!/usr/bin/env python3
"""Unit u-11-plsql-dunning: PKG_DUNNING + JOB_NIGHTLY_DUNNING ported to the
MongoDB service model.

Port of services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql and
the JOB_NIGHTLY_DUNNING scheduler entry (schema/04_jobs.sql).

Reads: invoices, tenants, subscriptions, dunningAttempts, notifications.
Writes: dunningAttempts, notifications, tenants/subscriptions (suspend),
subscriptionsHist (via the TRG_SUBSCRIPTIONS_HIST-equivalent hist writer),
billingAuditLog.

run_nightly_dunning() is the JOB_NIGHTLY_DUNNING equivalent: a service
entry point a scheduler would call nightly. It is DISABLED BY DEFAULT —
nothing schedules it in this offline batch; it exists so cutover can wire
a cron/task runner later. Never call it on import.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

import ow_util
from plans_service import _utc, _write_hist

_TENANT_STATUS = {10: "active", 20: "suspended"}


def _date(v) -> _dt.date | None:
    if v is None:
        return None
    return v.date() if isinstance(v, _dt.datetime) else v


def overdue_accounts(db, as_of: _dt.date) -> list[dict[str, Any]]:
    """pkg_dunning.fn_overdue_accounts: status-40 invoices issued before as_of."""
    rows = []
    for inv in db["invoices"].find(
        {"statusCd": 40, "issuedAt": {"$lt": _utc(as_of)}}
    ).sort([("issuedAt", 1), ("_id", 1)]):
        tenant = db["tenants"].find_one({"_id": inv.get("tenantId")})
        issued = _date(inv.get("issuedAt"))
        rows.append(
            {
                "tenant_id": inv.get("tenantId"),
                "invoice_id": inv["_id"],
                "total": ow_util.dec2(inv.get("total")),
                "days_overdue": (as_of - issued).days if issued else None,
                "tenant_status": _TENANT_STATUS.get(
                    (tenant or {}).get("statusCd"), "UNKNOWN"
                ),
            }
        )
    return rows


def schedule_dunning(db, as_of: _dt.date) -> int:
    """pkg_dunning.sp_schedule_dunning: one attempt row per overdue invoice."""
    scheduled = 0
    for inv in db["invoices"].find({"statusCd": 40}).sort(
        [("issuedAt", 1), ("_id", 1)]
    ):
        top = db["dunningAttempts"].find_one(
            {"invoiceId": inv["_id"]}, sort=[("attemptNo", -1)]
        )
        attempt = (top.get("attemptNo") or 0) + 1 if top else 1

        # TRUNC + weekend push-out (SAT +2, SUN +1).
        nxt = as_of
        if nxt.weekday() == 5:  # Saturday
            nxt += _dt.timedelta(days=2)
        elif nxt.weekday() == 6:  # Sunday
            nxt += _dt.timedelta(days=1)
        try:
            db["dunningAttempts"].insert_one(
                {
                    "_id": ow_util.md5_uuid(inv["_id"] + str(attempt)),
                    "tenantId": inv.get("tenantId"),
                    "invoiceId": inv["_id"],
                    "attemptNo": attempt,
                    "scheduledFor": _utc(nxt),
                    "statusCd": 10,
                }
            )
            scheduled += 1
        except Exception:  # noqa: BLE001, S110 — ON CONFLICT DO NOTHING, Oracle-legacy way
            pass
    ow_util.log_msg(
        db, "DUNNING", f"scheduled {scheduled} attempts as of {ow_util.dt2str(as_of)}"
    )
    return scheduled


def suspend_overdue(db, as_of: _dt.date) -> list[str]:
    """pkg_dunning.sp_suspend_overdue: suspend tenants with invoices overdue
    >= 14 days; idempotent suspension notification per tenant/day."""
    cutoff = as_of - _dt.timedelta(days=14)
    tenant_ids = sorted(
        {
            inv["tenantId"]
            for inv in db["invoices"].find(
                {"statusCd": 40, "issuedAt": {"$lte": _utc(cutoff)}},
                projection={"tenantId": 1},
            )
            if inv.get("tenantId")
        }
    )
    suspended = []
    for tenant_id in tenant_ids:
        tenant = db["tenants"].find_one({"_id": tenant_id})
        if not tenant or tenant.get("statusCd") != 10:
            continue
        db["tenants"].update_one({"_id": tenant_id}, {"$set": {"statusCd": 20}})
        for sub in db["subscriptions"].find(
            {"tenantId": tenant_id, "statusCd": 10}
        ):
            db["subscriptions"].update_one(
                {"_id": sub["_id"]},
                {"$set": {"statusCd": 20, "suspendedOn": _utc(as_of)}},
            )
            _write_hist(db, sub, "UPD")

        sent_at = _utc(as_of)
        if (
            db["notifications"].count_documents(
                {"tenantId": tenant_id, "kindCd": 3, "sentAt": sent_at}
            )
            == 0
        ):
            db["notifications"].insert_one(
                {
                    "_id": ow_util.md5_uuid(
                        tenant_id + "suspension" + as_of.isoformat()
                    ),
                    "tenantId": tenant_id,
                    "kindCd": 3,
                    "sentAt": sent_at,
                }
            )
        ow_util.log_msg(db, "DUNNING", f"suspended tenant={tenant_id}")
        suspended.append(tenant_id)
    return suspended


def run_nightly_dunning(db, as_of: _dt.date | None = None) -> dict[str, Any]:
    """JOB_NIGHTLY_DUNNING equivalent (schema/04_jobs.sql): schedule next
    attempts, then suspend overdue accounts.

    DISABLED BY DEFAULT — invoked only when a scheduler is wired at
    cutover; nothing calls this on import or on a timer in this batch.
    """
    as_of = as_of or _dt.datetime.now(_dt.timezone.utc).date()
    scheduled = schedule_dunning(db, as_of)
    suspended = suspend_overdue(db, as_of)
    return {"as_of": as_of.isoformat(), "scheduled": scheduled,
            "suspended": suspended}
