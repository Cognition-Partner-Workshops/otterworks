from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pymongo.client_session import ClientSession
from pymongo.database import Database

from app.documents import bson_date
from app.domain import EntitlementRow, PlanRow, SubscriptionRow


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

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self.database.client.start_session() as session, session.start_transaction():
            self.session = session
            try:
                yield
            finally:
                self.session = None

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
