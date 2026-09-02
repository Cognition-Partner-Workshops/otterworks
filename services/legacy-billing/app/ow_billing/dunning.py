"""Application-side port of PKG_DUNNING."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from bson import Decimal128
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from . import NS_VALUE
from . import plans, util

TENANT_STATUS = {10: "active", 20: "suspended"}
DUNNING_STATUS = {10: "scheduled", 20: "sent", 30: "skipped"}


def trunc(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    return datetime(value.year, value.month, value.day)


def _decimal(value) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))


def _status(value: int | None) -> str:
    return TENANT_STATUS.get(value, "UNKNOWN")


def _dunning_status(value: int | None) -> str:
    return DUNNING_STATUS.get(value, "UNKNOWN")


def fn_overdue_accounts(store, as_of: date | datetime) -> list[dict]:
    day = trunc(as_of)
    rows = store.coll("billing_invoices").aggregate(
        [
            {"$match": {"status_cd": 40}},
            {
                "$addFields": {
                    "_day": {
                        "$dateToString": {
                            "format": "%Y%m%d",
                            "date": "$issued_at",
                        }
                    }
                }
            },
            {"$match": {"_day": {"$lt": day.strftime("%Y%m%d")}}},
            {
                "$lookup": {
                    "from": f"{store.prefix}tenants",
                    "localField": "tenant_id",
                    "foreignField": "_id",
                    "as": "_tenant",
                }
            },
            {"$sort": {"issued_at": 1, "_id": 1}},
        ]
    )
    result = []
    for row in rows:
        tenant = next(iter(row.get("_tenant") or []), None)
        issued_at = trunc(row["issued_at"])
        result.append(
            {
                "tenant_id": row.get("tenant_id"),
                "invoice_id": row.get("id", row.get("_id")),
                "total": _decimal(row.get("total")),
                "days_overdue": (day - issued_at).days,
                "tenant_status": _status(tenant.get("status_cd") if tenant else None),
            }
        )
    return result


def sp_schedule_dunning(store, as_of: date | datetime) -> int:
    day = trunc(as_of)
    next_day = day + timedelta(days={5: 2, 6: 1}.get(day.weekday(), 0))
    attempts = store.coll("dunning_attempts")
    invoices = store.coll("billing_invoices").find(
        {"status_cd": 40}, {"id": 1, "_id": 1, "tenant_id": 1}
    ).sort([("issued_at", 1), ("_id", 1)])
    scheduled = 0
    for invoice in invoices:
        invoice_id = invoice.get("id", invoice["_id"])
        prior = attempts.find_one({"invoice_id": invoice_id}, sort=[("attempt_no", -1)])
        attempt = int(prior["attempt_no"]) + 1 if prior else 1
        identifier = util.f_md5_uuid(f"{invoice_id}{attempt}")
        try:
            attempts.insert_one(
                {
                    "_id": identifier,
                    "id": identifier,
                    "tenant_id": invoice.get("tenant_id"),
                    "invoice_id": invoice_id,
                    "attempt_no": attempt,
                    "scheduled_for": next_day,
                    "status_cd": 10,
                    "ns": NS_VALUE,
                }
            )
        except DuplicateKeyError:
            continue
        scheduled += 1
    util.log_msg(
        store,
        "DUNNING",
        f"scheduled {scheduled} attempts as of {util.f_dt2str(as_of)}",
    )
    return scheduled


def sp_suspend_overdue(store, as_of: date | datetime) -> list[str]:
    day = trunc(as_of)
    cutoff = (day - timedelta(days=14)).strftime("%Y%m%d")
    tenants = store.coll("tenants")
    subscriptions = store.coll("subscriptions")
    notifications = store.coll("notifications")
    tenant_ids = sorted(
        row["_id"]
        for row in store.coll("billing_invoices").aggregate(
            [
                {"$match": {"status_cd": 40}},
                {
                    "$addFields": {
                        "_day": {
                            "$dateToString": {
                                "format": "%Y%m%d",
                                "date": "$issued_at",
                            }
                        }
                    }
                },
                {"$match": {"_day": {"$lte": cutoff}}},
                {"$group": {"_id": "$tenant_id"}},
            ]
        )
    )
    suspended = []
    for tenant_id in tenant_ids:
        def txn(session):
            if tenants.find_one(
                {"_id": tenant_id, "status_cd": 10}, session=session
            ) is None:
                return False
            tenants.update_one(
                {"_id": tenant_id, "status_cd": 10},
                {"$set": {"status_cd": 20}},
                session=session,
            )
            active_subscriptions = list(
                subscriptions.find(
                    {"tenant_id": tenant_id, "status_cd": 10},
                    session=session,
                ).sort("_id", 1)
            )
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for prior in active_subscriptions:
                updated = subscriptions.find_one_and_update(
                    {"_id": prior["_id"], "status_cd": 10},
                    {"$set": {"status_cd": 20, "suspended_on": day}},
                    return_document=ReturnDocument.BEFORE,
                    session=session,
                )
                if updated is None:
                    raise RuntimeError("subscription changed concurrently")
                hist_id = plans._next_value(
                    store, util.SEQ_SUBSCRIPTIONS_HIST, session
                )
                subscriptions_history = {
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
                store.coll("subscriptions_history").insert_one(
                    subscriptions_history, session=session
                )
            if notifications.count_documents(
                {"tenant_id": tenant_id, "kind_cd": 3, "sent_at": day},
                session=session,
            ) == 0:
                identifier = util.f_md5_uuid(
                    f"{tenant_id}suspension{day:%Y-%m-%d}"
                )
                notifications.insert_one(
                    {
                        "_id": identifier,
                        "id": identifier,
                        "tenant_id": tenant_id,
                        "kind_cd": 3,
                        "sent_at": day,
                        "ns": NS_VALUE,
                    },
                    session=session,
                )
            return True

        with store.client.start_session() as session:
            changed = session.with_transaction(txn)
        if not changed:
            continue
        suspended.append(tenant_id)
        util.log_msg(store, "DUNNING", f"suspended tenant={tenant_id}")
    return suspended
