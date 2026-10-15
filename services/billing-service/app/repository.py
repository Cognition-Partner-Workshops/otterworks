from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, TypeVar
from uuid import UUID

from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database

from app.documents import bson_date, bson_decimal
from app.domain import (
    EntitlementRow,
    PlanRow,
    RatingResultRow,
    SubscriptionRow,
    UsageSummaryRow,
)

T = TypeVar("T")


class MissingReferenceError(LookupError):
    """The tenant or plan a subscription points at does not exist."""


def _as_date(value: datetime | None) -> date | None:
    return value.date() if value is not None else None


def _plan_row(document: dict[str, Any]) -> PlanRow:
    return PlanRow(
        plan_id=document["_id"],
        code=document["code"],
        tier=document["tier"],
        monthly_fee=Decimal(document["monthlyFee"].to_decimal()),
        included_units=document["includedUnits"],
        overage_rate=Decimal(document["overageRate"].to_decimal()),
        active=document["active"],
    )


def _subscription_row(document: dict[str, Any]) -> SubscriptionRow:
    return SubscriptionRow(
        subscription_id=document["_id"],
        tenant_id=document["tenantId"],
        plan_id=document["planId"],
        starts_on=document["startsOn"].date(),
        ends_on=_as_date(document.get("endsOn")),
        status=document["status"],
        suspended_on=_as_date(document.get("suspendedOn")),
    )


class MongoPlansRepository:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.session: ClientSession | None = None

    def run_in_transaction(self, operation: Callable[[], T]) -> T:
        """Run `operation` in one multi-document transaction. The driver retries transient
        write conflicts and unknown commit outcomes, re-running `operation` from scratch."""

        def callback(session: ClientSession) -> T:
            self.session = session
            try:
                return operation()
            finally:
                self.session = None

        with self.database.client.start_session() as session:
            return session.with_transaction(callback)

    def list_plans(self) -> list[PlanRow]:
        return [_plan_row(doc) for doc in self.database.plans.find(session=self.session)]

    def find_entitlements(self, tenant_id: UUID) -> list[EntitlementRow]:
        tenant = self.database.tenants.find_one(
            {"_id": tenant_id}, {"_id": 1}, session=self.session
        )
        if tenant is None:
            return []
        plans = {plan.plan_id: plan for plan in self.list_plans()}
        rows = []
        for subscription in self.list_subscriptions(tenant_id):
            plan = plans.get(subscription.plan_id)
            if plan is None:
                continue
            rows.append(
                EntitlementRow(
                    tenant_id=tenant_id,
                    plan_code=plan.code,
                    tier=plan.tier,
                    monthly_fee=plan.monthly_fee,
                    included_units=plan.included_units,
                    subscription_status=subscription.status,
                    ends_on=subscription.ends_on,
                    starts_on=subscription.starts_on,
                )
            )
        return rows

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        cursor = self.database.subscriptions.find({"tenantId": tenant_id}, session=self.session)
        return [_subscription_row(doc) for doc in cursor]

    def update_subscription(self, subscription_id: UUID, ends_on: date, status: str) -> None:
        self.database.subscriptions.update_one(
            {"_id": subscription_id},
            {"$set": {"endsOn": bson_date(ends_on), "status": status}},
            session=self.session,
        )

    def insert_subscription(
        self,
        subscription_id: UUID,
        tenant_id: UUID,
        plan_id: UUID,
        starts_on: date,
        status: str,
    ) -> None:
        for collection, key in (("tenants", tenant_id), ("plans", plan_id)):
            query = {"_id": key}
            found = self.database[collection].find_one(query, {"_id": 1}, session=self.session)
            if found is None:
                raise MissingReferenceError(f"{collection} {key} does not exist")
        self.database.subscriptions.insert_one(
            {
                "_id": subscription_id,
                "tenantId": tenant_id,
                "planId": plan_id,
                "startsOn": bson_date(starts_on),
                "status": status,
            },
            session=self.session,
        )


def _day_bounds(period_start: date, period_end: date) -> dict[str, datetime]:
    # occurred_at::date BETWEEN start AND end, with the legacy session timezone UTC.
    if period_end == date.max:
        return {"$gte": bson_date(period_start), "$lte": datetime.max.replace(tzinfo=UTC)}
    return {"$gte": bson_date(period_start), "$lt": bson_date(period_end + timedelta(days=1))}


class MongoRatingRepository(MongoPlansRepository):
    """Rating reads plans and subscriptions only through the Plans repository it extends;
    it owns usageEvents and ratingPeriods (rating_results embedded as `rating`)."""

    def sum_usage_units(self, tenant_id: UUID, period_start: date, period_end: date) -> int:
        pipeline = [
            {
                "$match": {
                    "tenantId": tenant_id,
                    "occurredAt": _day_bounds(period_start, period_end),
                }
            },
            {"$group": {"_id": None, "units": {"$sum": "$units"}}},
        ]
        rows = list(self.database.usageEvents.aggregate(pipeline, session=self.session))
        return int(rows[0]["units"]) if rows else 0

    def usage_by_kind(
        self, tenant_id: UUID, period_start: date, period_end: date
    ) -> list[UsageSummaryRow]:
        pipeline = [
            {
                "$match": {
                    "tenantId": tenant_id,
                    "occurredAt": _day_bounds(period_start, period_end),
                }
            },
            {"$group": {"_id": "$kind", "eventCount": {"$sum": 1}, "units": {"$sum": "$units"}}},
            {"$sort": {"_id": 1}},
        ]
        return [
            UsageSummaryRow(kind=row["_id"], event_count=row["eventCount"], units=int(row["units"]))
            for row in self.database.usageEvents.aggregate(pipeline, session=self.session)
        ]

    def sum_prior_rollover_units(
        self, tenant_id: UUID, window_start: date, period_start: date
    ) -> int:
        pipeline = [
            {
                "$match": {
                    "tenantId": tenant_id,
                    "periodStart": {
                        "$gte": bson_date(window_start),
                        "$lt": bson_date(period_start),
                    },
                    "rating": {"$exists": True},
                }
            },
            {"$group": {"_id": None, "rolloverUnits": {"$sum": "$rating.rolloverUnits"}}},
        ]
        rows = list(self.database.ratingPeriods.aggregate(pipeline, session=self.session))
        return int(rows[0]["rolloverUnits"]) if rows else 0

    def upsert_rating_period(
        self, tenant_id: UUID, period_id: UUID, period_start: date, period_end: date
    ) -> UUID:
        # ON CONFLICT (tenant_id, period_start) DO UPDATE SET period_end: an existing period
        # keeps its id, a new one gets the legacy md5 id.
        document = self.database.ratingPeriods.find_one_and_update(
            {"tenantId": tenant_id, "periodStart": bson_date(period_start)},
            {
                "$set": {"periodEnd": bson_date(period_end)},
                "$setOnInsert": {"_id": period_id},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"_id": 1},
            session=self.session,
        )
        return document["_id"]

    def upsert_rating_result(self, result: RatingResultRow, created_at: date) -> RatingResultRow:
        # ON CONFLICT (id) DO UPDATE touches only used, rollover, billable and overage; an
        # existing result (imported or finalized earlier) keeps its id, subscription, quota
        # and created_at. The persisted row is returned.
        rated = {
            "rating.usedUnits": result.used_units,
            "rating.rolloverUnits": result.rollover_units,
            "rating.billableUnits": result.billable_units,
            "rating.overageAmount": bson_decimal(result.overage_amount),
        }
        first_write = {
            "rating.id": result.result_id,
            "rating.subscriptionId": result.subscription_id,
            "rating.quotaUnits": result.quota_units,
            "rating.createdAt": bson_date(created_at),
        }
        updated = self.database.ratingPeriods.update_one(
            {"_id": result.period_id, "rating": {"$exists": True}},
            {"$set": rated},
            session=self.session,
        )
        if updated.matched_count == 0:
            self.database.ratingPeriods.update_one(
                {"_id": result.period_id},
                {"$set": {**first_write, **rated}},
                session=self.session,
            )
        persisted = self.find_rating_result(result.period_id)
        if persisted is None:
            raise LookupError(f"rating period {result.period_id} vanished during finalize")
        return persisted

    def find_rating_result(self, period_id: UUID) -> RatingResultRow | None:
        document = self.database.ratingPeriods.find_one({"_id": period_id}, session=self.session)
        if document is None or "rating" not in document:
            return None
        rating = document["rating"]
        return RatingResultRow(
            period_id=document["_id"],
            result_id=rating["id"],
            subscription_id=rating["subscriptionId"],
            used_units=rating["usedUnits"],
            quota_units=rating["quotaUnits"],
            rollover_units=rating["rolloverUnits"],
            billable_units=rating["billableUnits"],
            overage_amount=Decimal(rating["overageAmount"].to_decimal()),
        )
