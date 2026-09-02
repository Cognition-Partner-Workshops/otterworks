"""App-side port of OW_BILLING.PKG_RATING (mapping D10, unit U7).

The package globals (g_used_units, g_quota_units, ...) become fields of the
`Rating` return value. The usage sum is a `$match`/`$group` aggregation that keeps
the PL/SQL `TO_CHAR(occurred_at, 'YYYYMMDD')` string-window comparison; the
rollover/tier arithmetic keeps Oracle's NULL-propagating NVL/LEAST/GREATEST/ROUND.

Every read and write goes through a `RatingStore`, which names the collections the
caller owns (the shared U5 set, or a `replay_u7_` clone for Tier-4 replay).
"""

from __future__ import annotations

import calendar
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from bson import Decimal128, Int64
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from . import NS_VALUE

KIND_DECODE = {1: "api", 2: "storage", 3: "compute"}
KIND_UNKNOWN = "UNKNOWN"
FIRST_TIER_UNITS = 101
SECOND_TIER_MULTIPLIER = Decimal("1.5")
AUDIT_SEQUENCE = "SEQ_BILLING_AUDIT_LOG"

Number = Decimal | None


# --- Oracle NUMBER semantics --------------------------------------------------


def nvl(value: Number, default: Number) -> Number:
    return default if value is None else value


def least(*values: Number) -> Number:
    present = [v for v in values if v is not None]
    return min(present) if len(present) == len(values) else None


def greatest(*values: Number) -> Number:
    present = [v for v in values if v is not None]
    return max(present) if len(present) == len(values) else None


def oracle_round(value: Number, places: int = 0) -> Number:
    if value is None:
        return None
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _add(a: Number, b: Number) -> Number:
    return None if a is None or b is None else a + b


def _sub(a: Number, b: Number) -> Number:
    return None if a is None or b is None else a - b


def _mul(a: Number, b: Number) -> Number:
    return None if a is None or b is None else a * b


def to_decimal(value: Any) -> Number:
    if value is None:
        return None
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def add_months(day: datetime, months: int) -> datetime:
    """Oracle ADD_MONTHS: a last-day-of-month input yields the last day of the result."""
    year = day.year + (day.month - 1 + months) // 12
    month = (day.month - 1 + months) % 12 + 1
    last_in = calendar.monthrange(day.year, day.month)[1]
    last_out = calendar.monthrange(year, month)[1]
    dom = last_out if day.day == last_in else min(day.day, last_out)
    return day.replace(year=year, month=month, day=dom)


def as_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    return datetime(value.year, value.month, value.day)  # noqa: DTZ001 - naive UTC, like the U5 loader


def md5_uuid(text: str) -> str:
    """pkg_ow_util.f_md5_uuid: lower-case MD5 hex laid out as 8-4-4-4-12."""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _days_between(later: datetime, earlier: datetime) -> Decimal:
    """Oracle DATE subtraction: fractional days."""
    delta = later - earlier
    return Decimal(delta.days) + Decimal(delta.seconds) / Decimal(86400)


# --- storage -----------------------------------------------------------------


@dataclass(frozen=True)
class RatingStore:
    """Collections the rating module reads and writes. `prefix` is empty for the
    shared U5 set and `replay_u7_` for the Tier-4 clone."""

    db: Database
    prefix: str = ""

    def coll(self, name: str):
        return self.db[f"{self.prefix}{name}"]

    @property
    def subscriptions(self):
        return self.coll("subscriptions")

    @property
    def plans(self):
        return self.coll("plans")

    @property
    def usage_events(self):
        return self.coll("usage_events")

    @property
    def rating_periods(self):
        return self.coll("rating_periods")

    @property
    def billing_audit_log(self):
        return self.coll("billing_audit_log")

    @property
    def counters(self):
        return self.coll("counters")


def _next_log_id(store: RatingStore) -> Int64:
    if store.counters.find_one({"_id": AUDIT_SEQUENCE}) is None:
        _reconcile_log_sequence(store)
    counter = store.counters.find_one_and_update(
        {"_id": AUDIT_SEQUENCE},
        {"$inc": {"value": Int64(1)}, "$setOnInsert": {"ns": NS_VALUE}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return Int64(counter["value"])


def _reconcile_log_sequence(store: RatingStore) -> None:
    """Move the sequence past every log_id already present (the shared `counters` is not
    guaranteed to be seeded for SEQ_BILLING_AUDIT_LOG while the audit log is)."""
    top = store.billing_audit_log.find_one(sort=[("log_id", DESCENDING)])
    highest = Int64(top["log_id"]) if top else Int64(0)
    store.counters.update_one(
        {"_id": AUDIT_SEQUENCE},
        {"$max": {"value": highest}, "$setOnInsert": {"ns": NS_VALUE}},
        upsert=True,
    )


def log_msg(store: RatingStore, module: str, message: str) -> None:
    """pkg_ow_util.log_msg: autonomous-transaction logger; a failure to log never
    reaches the caller (WHEN OTHERS THEN ROLLBACK)."""
    try:
        for attempt in range(2):
            log_id = _next_log_id(store)
            try:
                store.billing_audit_log.insert_one(
                    {
                        "_id": log_id,
                        "log_id": log_id,
                        "logged_at": datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0),
                        "module": module[:30],
                        "message": message[:4000],
                        "ns": NS_VALUE,
                    }
                )
                return
            except DuplicateKeyError:
                if attempt:
                    raise
                _reconcile_log_sequence(store)
    except PyMongoError:
        return


# --- compute_rating -------------------------------------------------------------


@dataclass(frozen=True)
class Rating:
    """The former pkg_rating globals, as one immutable return value."""

    tenant_id: str
    period_start: datetime
    period_end: datetime
    used_units: Decimal
    quota_units: Number
    rollover_units: Number
    billable_units: Number
    first_tier_units: Number
    second_tier_units: Number
    overage_amount: Number

    def as_row(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "used_units": self.used_units,
            "quota_units": self.quota_units,
            "rollover_units": self.rollover_units,
            "billable_units": self.billable_units,
            "first_tier_units": self.first_tier_units,
            "second_tier_units": self.second_tier_units,
            "overage_amount": self.overage_amount,
        }


def covering_subscription(
    store: RatingStore, tenant_id: str, period_start: datetime, period_end: datetime
) -> dict[str, Any] | None:
    return store.subscriptions.find_one(
        {
            "tenant_id": tenant_id,
            "starts_on": {"$lte": period_end},
            "$or": [{"ends_on": None}, {"ends_on": {"$gte": period_start}}],
        },
        sort=[("starts_on", DESCENDING)],
    )


def usage_sum_pipeline(tenant_id: str, period_start: datetime, period_end: datetime) -> list[dict]:
    """SUM(NVL(units, 0)) over TO_CHAR(occurred_at,'YYYYMMDD') BETWEEN the period bounds."""
    start_key = period_start.strftime("%Y%m%d")
    end_key = period_end.strftime("%Y%m%d")
    return [
        {"$match": {"tenant_id": tenant_id}},
        {
            "$addFields": {
                "_day": {"$dateToString": {"format": "%Y%m%d", "date": "$occurred_at"}}
            }
        },
        {"$match": {"_day": {"$gte": start_key, "$lte": end_key}}},
        {"$group": {"_id": None, "used_units": {"$sum": {"$ifNull": ["$units", 0]}}}},
    ]


def prior_rollover_pipeline(tenant_id: str, period_start: datetime) -> list[dict]:
    """SUM(NVL(rr.rollover_units, 0)) over the prior three months' rating_results."""
    return [
        {
            "$match": {
                "tenant_id": tenant_id,
                "period_start": {"$lt": period_start, "$gte": add_months(period_start, -3)},
            }
        },
        {"$unwind": "$results"},
        {"$group": {"_id": None, "prior": {"$sum": {"$ifNull": ["$results.rollover_units", 0]}}}},
    ]


def _single_sum(cursor: Any, field: str) -> Decimal:
    for row in cursor:
        return to_decimal(row[field]) or Decimal(0)
    return Decimal(0)


def compute_rating(
    store: RatingStore, tenant_id: str, period_start: date | datetime, period_end: date | datetime
) -> Rating:
    p_start, p_end = as_datetime(period_start), as_datetime(period_end)

    sub = covering_subscription(store, tenant_id, p_start, p_end)
    sub_status = to_decimal(sub.get("status_cd")) if sub else None
    suspended_on = sub.get("suspended_on") if sub else None
    plan = store.plans.find_one({"_id": sub.get("plan_id")}) if sub else None
    included = to_decimal(plan.get("included_units")) if plan else None
    rate = to_decimal(plan.get("overage_rate")) if plan else None

    used = _single_sum(store.usage_events.aggregate(usage_sum_pipeline(tenant_id, p_start, p_end)),
                       "used_units")
    prior = _single_sum(store.rating_periods.aggregate(prior_rollover_pipeline(tenant_id, p_start)),
                        "prior")

    prior = least(nvl(_mul(Decimal(2), included), prior), prior)

    quota = included
    rollover = least(prior, nvl(_mul(included, Decimal(2)), prior))
    billable = greatest(nvl(_sub(_sub(used, rollover), included), Decimal(0)), Decimal(0))
    first_tier = least(billable, Decimal(FIRST_TIER_UNITS))
    second_tier = greatest(_sub(billable, Decimal(FIRST_TIER_UNITS)), Decimal(0))
    overage = oracle_round(
        _add(_mul(first_tier, rate), _mul(_mul(second_tier, rate), SECOND_TIER_MULTIPLIER)), 2
    )

    if (
        sub_status == 20
        and suspended_on is not None
        and p_start <= suspended_on <= p_end
    ):
        factor = (_days_between(p_end, suspended_on) + 1) / (_days_between(p_end, p_start) + 1)
        billable = oracle_round(_mul(billable, factor))
        overage = oracle_round(_mul(overage, factor), 2)

    log_msg(
        store,
        "RATING",
        f"compute tenant={tenant_id} used={nvl(used, Decimal(-1))} "
        f"billable={nvl(billable, Decimal(-1))}",
    )
    return Rating(
        tenant_id=tenant_id,
        period_start=p_start,
        period_end=p_end,
        used_units=used,
        quota_units=quota,
        rollover_units=rollover,
        billable_units=billable,
        first_tier_units=first_tier,
        second_tier_units=second_tier,
        overage_amount=overage,
    )


# --- entrypoints -----------------------------------------------------------------


def fn_usage_rating(
    store: RatingStore, tenant_id: str, period_start: date | datetime, period_end: date | datetime
) -> list[dict[str, Any]]:
    return [compute_rating(store, tenant_id, period_start, period_end).as_row()]


def usage_summary_pipeline(tenant_id: str, period_start: datetime, period_end: datetime) -> list[dict]:
    start_key = period_start.strftime("%Y%m%d")
    end_key = period_end.strftime("%Y%m%d")
    branches = [
        {"case": {"$eq": ["$kind_cd", code]}, "then": kind} for code, kind in KIND_DECODE.items()
    ]
    return [
        {"$match": {"tenant_id": tenant_id}},
        {
            "$addFields": {
                "_day": {"$dateToString": {"format": "%Y%m%d", "date": "$occurred_at"}}
            }
        },
        {"$match": {"_day": {"$gte": start_key, "$lte": end_key}}},
        {
            "$group": {
                "_id": {"$switch": {"branches": branches, "default": KIND_UNKNOWN}},
                "event_count": {"$sum": 1},
                "units": {"$sum": {"$ifNull": ["$units", 0]}},
            }
        },
        {"$sort": {"_id": ASCENDING}},
        {"$project": {"_id": 0, "kind": "$_id", "event_count": 1, "units": 1}},
    ]


def fn_usage_summary(
    store: RatingStore, tenant_id: str, period_start: date | datetime, period_end: date | datetime
) -> list[dict[str, Any]]:
    p_start, p_end = as_datetime(period_start), as_datetime(period_end)
    return [
        {
            "kind": row["kind"],
            "event_count": Decimal(row["event_count"]),
            "units": to_decimal(row["units"]) or Decimal(0),
        }
        for row in store.usage_events.aggregate(usage_summary_pipeline(tenant_id, p_start, p_end))
    ]


def _long(value: Number) -> Int64 | None:
    return None if value is None else Int64(int(value))


def _money(value: Number) -> Decimal128 | None:
    return None if value is None else Decimal128(value.quantize(Decimal("0.01")))


class RatingIntegrityError(ValueError):
    """ORA-01400: a NOT NULL column of rating_results would receive NULL."""


def sp_finalize_rating(
    store: RatingStore, tenant_id: str, period_start: date | datetime, period_end: date | datetime
) -> dict[str, Any]:
    """Upsert the tenant's period and its single embedded results[] element; returns the
    rating_periods document as stored.

    The legacy procedure runs inside the caller's transaction, so a failed finalization
    leaves nothing behind. Here every read happens first and the period + result land in
    ONE document write (an upsert that also pushes the result, or a positional refresh of
    the existing result), so there is no partial state to roll back.
    """
    p_start, p_end = as_datetime(period_start), as_datetime(period_end)
    period_id = md5_uuid(f"{tenant_id}{p_start.strftime('%Y-%m-%d')}")
    period_key = {"tenant_id": tenant_id, "period_start": p_start}

    sub = covering_subscription(store, tenant_id, p_start, p_end)
    sub_id = sub.get("id") if sub else None

    rating = compute_rating(store, tenant_id, p_start, p_end)
    result_id = md5_uuid(period_id)
    banked = greatest(_sub(rating.quota_units, rating.used_units), Decimal(0))

    result = {
        "id": result_id,
        "period_id": period_id,
        "subscription_id": sub_id,
        "used_units": _long(rating.used_units),
        "quota_units": _long(rating.quota_units),
        "rollover_units": _long(banked),
        "billable_units": _long(rating.billable_units),
        "overage_amount": _money(rating.overage_amount),
        "created_at": p_end,
    }
    missing = [k for k, v in result.items() if v is None]
    if missing:
        raise RatingIntegrityError(
            f"rating_results.{missing[0]} cannot be NULL (tenant={tenant_id} period={period_id})"
        )
    # UPDATE rating_results SET the four amounts WHERE id = v_result_id
    refresh = {
        "$set": {
            "period_end": p_end,
            **{f"results.$.{k}": result[k] for k in
               ("used_units", "rollover_units", "billable_units", "overage_amount")},
        }
    }

    def _refresh() -> bool:
        return store.rating_periods.update_one({**period_key, "results.id": result_id}, refresh).matched_count == 1

    if not _refresh():
        # INSERT rating_periods (or UPDATE period_end) + INSERT rating_results, atomically:
        # the `results.id != result_id` guard makes a racing writer's append surface as a
        # DuplicateKeyError on uq_rating_periods, after which the refresh path applies.
        try:
            store.rating_periods.update_one(
                {**period_key, "results.id": {"$ne": result_id}},
                {
                    "$set": {"period_end": p_end},
                    "$setOnInsert": {"_id": period_id, "id": period_id, **period_key, "ns": NS_VALUE},
                    "$push": {"results": result},
                },
                upsert=True,
            )
        except DuplicateKeyError:
            _refresh()
    log_msg(store, "RATING", f"finalized period={period_id}")
    return store.rating_periods.find_one(period_key)


def rating_result_rows(store: RatingStore, tenant_id: str, period_start: date | datetime) -> list[dict[str, Any]]:
    """The finalize probe: rating_results joined to its period."""
    doc = store.rating_periods.find_one({"tenant_id": tenant_id, "period_start": as_datetime(period_start)})
    if not doc:
        return []
    return [
        {
            "used_units": to_decimal(r.get("used_units")),
            "quota_units": to_decimal(r.get("quota_units")),
            "rollover_units": to_decimal(r.get("rollover_units")),
            "billable_units": to_decimal(r.get("billable_units")),
            "overage_amount": to_decimal(r.get("overage_amount")),
        }
        for r in doc.get("results", [])
    ]
