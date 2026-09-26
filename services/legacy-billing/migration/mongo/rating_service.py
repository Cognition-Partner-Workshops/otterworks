#!/usr/bin/env python3
"""Unit u-09-plsql-rating: PKG_RATING ported to the MongoDB service model.

Port of services/legacy-billing/db/oracle/packages/03_pkg_rating.sql.
The package globals become the `RatingState` dict returned by
compute_rating(): the package only ever computes for one tenant/period at
a time, so the mutable-globals contract collapses to one call's result.

Reads: subscriptions, plans, usageEvents, ratingPeriods, ratingResults.
Writes (sp_finalize_rating only): ratingPeriods, ratingResults,
billingAuditLog. Deterministic _ids via ow_util.md5_uuid.

Usage (repo root):
    python3 rating_service.py            # nothing; imported by parity
"""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Any

import ow_util
from plans_service import _latest_covering_sub, _utc


def _add_months(d: _dt.date, months: int) -> _dt.date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    day = min(d.day, [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return _dt.date(y, m, day)


def _dec(v) -> Decimal | None:
    if v is None:
        return None
    return v.to_decimal() if hasattr(v, "to_decimal") else Decimal(str(v))


def compute_rating(db, tenant_id: str, period_start: _dt.date,
                   period_end: _dt.date) -> dict[str, Any]:
    """pkg_rating.compute_rating: the g_* globals as one result dict."""
    g: dict[str, Any] = {
        "tenant_id": tenant_id,
        "period_start": period_start,
        "period_end": period_end,
        "used_units": 0,
        "quota_units": None,
        "rollover_units": None,
        "billable_units": None,
        "first_tier_units": None,
        "second_tier_units": None,
        "overage_amount": None,
    }

    sub = _latest_covering_sub(db, tenant_id, period_start, period_end)
    plan = db["plans"].find_one({"_id": sub.get("planId")}) if sub else None
    included = plan.get("includedUnits") if plan else None
    rate = _dec(plan.get("overageRate")) if plan else None

    # Period usage sum. TO_CHAR 'YYYYMMDD' compare == inclusive date range.
    for ev in db["usageEvents"].find({"tenantId": tenant_id}):
        occ = ev.get("occurredAt")
        occ_d = occ.date() if isinstance(occ, _dt.datetime) else occ
        if occ_d is not None and period_start <= occ_d <= period_end:
            g["used_units"] += ev.get("units") or 0

    # Banked rollover from rating results in the prior 3 months.
    prior = 0
    period_ids = [
        p["_id"]
        for p in db["ratingPeriods"].find(
            {
                "tenantId": tenant_id,
                "periodStart": {
                    "$gte": _utc(_add_months(period_start, -3)),
                    "$lt": _utc(period_start),
                },
            },
            projection={"_id": 1},
        )
    ]
    for r in db["ratingResults"].find(
        {"periodId": {"$in": period_ids}}, projection={"rolloverUnits": 1}
    ):
        prior += r.get("rolloverUnits") or 0
    # Postgres LEAST/GREATEST NULL semantics preserved per the source.
    prior = min(2 * included if included is not None else prior, prior)

    g["quota_units"] = included
    g["rollover_units"] = min(prior, included * 2 if included is not None else prior)
    diff = (
        g["used_units"] - g["rollover_units"] - included
        if included is not None
        else None
    )
    g["billable_units"] = max(diff or 0, 0)
    # Tier break at 101 units.
    g["first_tier_units"] = min(g["billable_units"], 101)
    g["second_tier_units"] = max(g["billable_units"] - 101, 0)
    g["overage_amount"] = (
        None
        if rate is None
        else ow_util.money_round(
            g["first_tier_units"] * rate + g["second_tier_units"] * rate * Decimal("1.5"),
            2,
        )
    )

    suspended = sub.get("suspendedOn") if sub else None
    susp_d = suspended.date() if isinstance(suspended, _dt.datetime) else suspended
    if (
        sub
        and sub.get("statusCd") == 20
        and susp_d is not None
        and period_start <= susp_d <= period_end
    ):
        num = (period_end - susp_d).days + 1
        den = (period_end - period_start).days + 1
        factor = Decimal(num) / Decimal(den)
        g["billable_units"] = int(
            ow_util.money_round(Decimal(g["billable_units"]) * factor, 0)
        )
        g["overage_amount"] = (
            None
            if g["overage_amount"] is None
            else ow_util.money_round(g["overage_amount"] * factor, 2)
        )

    ow_util.log_msg(
        db,
        "RATING",
        f"compute tenant={tenant_id} used={g['used_units'] if g['used_units'] is not None else -1}"
        f" billable={g['billable_units'] if g['billable_units'] is not None else -1}",
    )
    return g


def usage_rating(db, tenant_id: str, period_start: _dt.date,
                 period_end: _dt.date) -> list[dict[str, Any]]:
    """pkg_rating.fn_usage_rating: one-row cursor equivalent."""
    g = compute_rating(db, tenant_id, period_start, period_end)
    return [
        {
            "tenant_id": g["tenant_id"],
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "used_units": g["used_units"],
            "quota_units": g["quota_units"],
            "rollover_units": g["rollover_units"],
            "billable_units": g["billable_units"],
            "first_tier_units": g["first_tier_units"],
            "second_tier_units": g["second_tier_units"],
            "overage_amount": ow_util.dec2(g["overage_amount"]),
        }
    ]


def usage_summary(db, tenant_id: str, period_start: _dt.date,
                  period_end: _dt.date) -> list[dict[str, Any]]:
    """pkg_rating.fn_usage_summary: GROUP BY kind over the period."""
    buckets: dict[int, list[int]] = {}
    for ev in db["usageEvents"].find({"tenantId": tenant_id}):
        occ = ev.get("occurredAt")
        occ_d = occ.date() if isinstance(occ, _dt.datetime) else occ
        if occ_d is not None and period_start <= occ_d <= period_end:
            agg = buckets.setdefault(int(ev.get("kindCd") or 0), [0, 0])
            agg[0] += 1
            agg[1] += ev.get("units") or 0
    rows = [
        {
            "kind": ow_util.code_desc(db, "USAGE_KIND", k),
            "event_count": v[0],
            "units": v[1],
        }
        for k, v in buckets.items()
    ]
    rows.sort(key=lambda r: r["kind"])
    return rows


def finalize_rating(db, tenant_id: str, period_start: _dt.date,
                    period_end: _dt.date) -> None:
    """pkg_rating.sp_finalize_rating: upsert period + result."""
    period_id = ow_util.md5_uuid(tenant_id + period_start.isoformat())
    sub = _latest_covering_sub(db, tenant_id, period_start, period_end)
    sub_id = sub["_id"] if sub else None

    # INSERT-or-update upsert keyed by _id (the DUP_VAL_ON_INDEX fallback
    # updates by tenant+period_start, which is the same document).
    if db["ratingPeriods"].count_documents({"_id": period_id}) == 0:
        db["ratingPeriods"].insert_one(
            {
                "_id": period_id,
                "tenantId": tenant_id,
                "periodStart": _utc(period_start),
                "periodEnd": _utc(period_end),
            }
        )
    else:
        db["ratingPeriods"].update_one(
            {"_id": period_id}, {"$set": {"periodEnd": _utc(period_end)}}
        )

    g = compute_rating(db, tenant_id, period_start, period_end)
    result_id = ow_util.md5_uuid(period_id)
    fields = {
        "usedUnits": g["used_units"],
        "quotaUnits": g["quota_units"],
        # The Oracle INSERT stores GREATEST(quota - used, 0), not the
        # compute-time rollover figure.
        "rolloverUnits": max(
            (g["quota_units"] or 0) - g["used_units"], 0
        )
        if g["quota_units"] is not None
        else 0,
        "billableUnits": g["billable_units"],
        "overageAmount": None
        if g["overage_amount"] is None
        else _to_decimal128(g["overage_amount"]),
    }
    if db["ratingResults"].count_documents({"_id": result_id}) == 0:
        db["ratingResults"].insert_one(
            {
                "_id": result_id,
                "periodId": period_id,
                "subscriptionId": sub_id,
                "createdAt": _utc(period_end),
                **{k: v for k, v in fields.items() if v is not None},
            }
        )
    else:
        db["ratingResults"].update_one({"_id": result_id}, {"$set": fields})
    ow_util.log_msg(db, "RATING", f"finalized period={period_id}")


def _to_decimal128(d: Decimal):
    from bson import Decimal128  # lazy

    return Decimal128(str(d))
