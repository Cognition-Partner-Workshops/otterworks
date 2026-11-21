from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

import psycopg

from app.domain import (
    EntitlementRow,
    PlanRow,
    PriorRollover,
    Rating,
    RatingResultRow,
    RatingSubscription,
    SubscriptionRow,
    UsageEvent,
)


class PostgresPlansRepository:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def list_plans(self) -> list[PlanRow]:
        rows = self.connection.execute(
            """
            SELECT id, code, tier, monthly_fee, included_units, overage_rate, active
            FROM billing_svc.plans
            """
        ).fetchall()
        return [
            PlanRow(
                plan_id=row["id"],
                code=row["code"],
                tier=row["tier"],
                monthly_fee=Decimal(row["monthly_fee"]),
                included_units=row["included_units"],
                overage_rate=Decimal(row["overage_rate"]),
                active=row["active"],
            )
            for row in rows
        ]

    def find_entitlements(self, tenant_id: UUID) -> list[EntitlementRow]:
        rows = self.connection.execute(
            """
            SELECT t.id AS tenant_id, p.code AS plan_code, p.tier,
                   p.monthly_fee, p.included_units, s.status,
                   s.starts_on, s.ends_on
            FROM billing_svc.tenants t
            JOIN billing_svc.subscriptions s ON s.tenant_id = t.id
            JOIN billing_svc.plans p ON p.id = s.plan_id
            WHERE t.id = %s
            """,
            (tenant_id,),
        ).fetchall()
        return [
            EntitlementRow(
                tenant_id=row["tenant_id"],
                plan_code=row["plan_code"],
                tier=row["tier"],
                monthly_fee=Decimal(row["monthly_fee"]),
                included_units=row["included_units"],
                subscription_status=row["status"],
                ends_on=row["ends_on"],
                starts_on=row["starts_on"],
            )
            for row in rows
        ]

    def list_subscriptions(self, tenant_id: UUID) -> list[SubscriptionRow]:
        rows = self.connection.execute(
            """
            SELECT id, tenant_id, plan_id, starts_on, ends_on, status, suspended_on
            FROM billing_svc.subscriptions
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        ).fetchall()
        return [
            SubscriptionRow(
                subscription_id=row["id"],
                tenant_id=row["tenant_id"],
                plan_id=row["plan_id"],
                starts_on=row["starts_on"],
                ends_on=row["ends_on"],
                status=row["status"],
                suspended_on=row["suspended_on"],
            )
            for row in rows
        ]

    def update_subscription(self, subscription_id: UUID, ends_on: date, status: str) -> None:
        self.connection.execute(
            """
            UPDATE billing_svc.subscriptions
            SET ends_on = %s, status = %s
            WHERE id = %s
            """,
            (ends_on, status, subscription_id),
        )

    def insert_subscription(
        self,
        subscription_id: UUID,
        tenant_id: UUID,
        plan_id: UUID,
        starts_on: date,
        status: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO billing_svc.subscriptions
                (id, tenant_id, plan_id, starts_on, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (subscription_id, tenant_id, plan_id, starts_on, status),
        )


class PostgresRatingRepository:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def list_rating_subscriptions(self, tenant_id: UUID) -> list[RatingSubscription]:
        rows = self.connection.execute(
            """
            SELECT s.id, s.plan_id, s.starts_on, s.ends_on, s.status, s.suspended_on,
                   p.included_units, p.overage_rate
            FROM billing_svc.subscriptions s
            JOIN billing_svc.plans p ON p.id = s.plan_id
            WHERE s.tenant_id = %s
            """,
            (tenant_id,),
        ).fetchall()
        return [
            RatingSubscription(
                subscription_id=row["id"],
                plan_id=row["plan_id"],
                starts_on=row["starts_on"],
                ends_on=row["ends_on"],
                status=row["status"],
                suspended_on=row["suspended_on"],
                included_units=row["included_units"],
                overage_rate=Decimal(row["overage_rate"]),
            )
            for row in rows
        ]

    def list_usage_events(
        self, tenant_id: UUID, period_start: date, period_end: date
    ) -> list[UsageEvent]:
        lower = datetime.combine(period_start - timedelta(days=1), time.min, tzinfo=UTC)
        upper = datetime.combine(period_end + timedelta(days=2), time.min, tzinfo=UTC)
        rows = self.connection.execute(
            """
            SELECT occurred_at, units, kind
            FROM billing_svc.usage_events
            WHERE tenant_id = %s AND occurred_at >= %s AND occurred_at < %s
            """,
            (tenant_id, lower, upper),
        ).fetchall()
        return [
            UsageEvent(occurred_at=row["occurred_at"], units=row["units"], kind=row["kind"])
            for row in rows
        ]

    def list_prior_rollovers(self, tenant_id: UUID, before: date) -> list[PriorRollover]:
        lower = before - timedelta(days=124)
        rows = self.connection.execute(
            """
            SELECT rp.period_start, rr.rollover_units
            FROM billing_svc.rating_results rr
            JOIN billing_svc.rating_periods rp ON rp.id = rr.period_id
            WHERE rp.tenant_id = %s
              AND rp.period_start < %s
              AND rp.period_start >= %s
            """,
            (tenant_id, before, lower),
        ).fetchall()
        return [
            PriorRollover(period_start=row["period_start"], rollover_units=row["rollover_units"])
            for row in rows
        ]

    def upsert_rating_period(
        self, period_id: UUID, tenant_id: UUID, period_start: date, period_end: date
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO billing_svc.rating_periods (id, tenant_id, period_start, period_end)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tenant_id, period_start) DO UPDATE
              SET period_end = EXCLUDED.period_end
            """,
            (period_id, tenant_id, period_start, period_end),
        )

    def upsert_rating_result(
        self,
        result_id: UUID,
        period_id: UUID,
        subscription_id: UUID | None,
        rating: Rating,
        rollover_units: int,
        created_at: datetime,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO billing_svc.rating_results (
                id, period_id, subscription_id, used_units, quota_units, rollover_units,
                billable_units, overage_amount, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                used_units = EXCLUDED.used_units,
                rollover_units = EXCLUDED.rollover_units,
                billable_units = EXCLUDED.billable_units,
                overage_amount = EXCLUDED.overage_amount
            """,
            (
                result_id,
                period_id,
                subscription_id,
                rating.used_units,
                rating.quota_units,
                rollover_units,
                rating.billable_units,
                rating.overage_amount,
                created_at,
            ),
        )

    def find_rating_results(self, tenant_id: UUID, period_start: date) -> list[RatingResultRow]:
        rows = self.connection.execute(
            """
            SELECT rr.used_units, rr.quota_units, rr.rollover_units, rr.billable_units,
                   rr.overage_amount
            FROM billing_svc.rating_results rr
            JOIN billing_svc.rating_periods rp ON rp.id = rr.period_id
            WHERE rp.tenant_id = %s AND rp.period_start = %s
            """,
            (tenant_id, period_start),
        ).fetchall()
        return [
            RatingResultRow(
                used_units=row["used_units"],
                quota_units=row["quota_units"],
                rollover_units=row["rollover_units"],
                billable_units=row["billable_units"],
                overage_amount=Decimal(row["overage_amount"]),
            )
            for row in rows
        ]
