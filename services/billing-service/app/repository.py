from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg

from app.domain import (
    EntitlementRow,
    InvoiceLineRow,
    InvoiceTotals,
    InvoicingCreditNote,
    InvoicingOverage,
    InvoicingPlan,
    InvoicingPriorRollover,
    InvoicingSubscription,
    PlanRow,
    SubscriptionRow,
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


# --- invoicing ----------------------------------------------------------------


class PostgresInvoicingRepository:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def list_invoicing_subscriptions(self, tenant_id: UUID) -> list[InvoicingSubscription]:
        rows = self.connection.execute(
            """
            SELECT s.id, s.starts_on, s.ends_on, s.status, s.suspended_on,
                   p.code, p.monthly_fee, p.included_units, p.overage_rate
            FROM billing_svc.subscriptions s
            JOIN billing_svc.plans p ON p.id = s.plan_id
            WHERE s.tenant_id = %s
            """,
            (tenant_id,),
        ).fetchall()
        return [
            InvoicingSubscription(
                subscription_id=row["id"],
                starts_on=row["starts_on"],
                ends_on=row["ends_on"],
                status=row["status"],
                suspended_on=row["suspended_on"],
                plan=InvoicingPlan(
                    code=row["code"],
                    monthly_fee=Decimal(row["monthly_fee"]),
                    included_units=row["included_units"],
                    overage_rate=Decimal(row["overage_rate"]),
                ),
            )
            for row in rows
        ]

    def tenant_tax_exempt(self, tenant_id: UUID) -> bool | None:
        row = self.connection.execute(
            "SELECT tax_exempt FROM billing_svc.tenants WHERE id = %s", (tenant_id,)
        ).fetchone()
        return row["tax_exempt"] if row else None

    def sum_usage_units(self, tenant_id: UUID, period_start: date, period_end: date) -> int:
        row = self.connection.execute(
            """
            SELECT COALESCE(sum(units), 0)::integer AS units
            FROM billing_svc.usage_events
            WHERE tenant_id = %s
              AND (occurred_at AT TIME ZONE 'UTC')::date BETWEEN %s AND %s
            """,
            (tenant_id, period_start, period_end),
        ).fetchone()
        return row["units"]

    def list_prior_rollovers(self, tenant_id: UUID) -> list[InvoicingPriorRollover]:
        rows = self.connection.execute(
            """
            SELECT rp.period_start, rr.rollover_units
            FROM billing_svc.rating_results rr
            JOIN billing_svc.rating_periods rp ON rp.id = rr.period_id
            WHERE rp.tenant_id = %s
            """,
            (tenant_id,),
        ).fetchall()
        return [InvoicingPriorRollover(row["period_start"], row["rollover_units"]) for row in rows]

    def list_open_credit_notes(self, tenant_id: UUID) -> list[InvoicingCreditNote]:
        rows = self.connection.execute(
            """
            SELECT id, issued_on, remaining_amount
            FROM billing_svc.credit_notes
            WHERE tenant_id = %s AND remaining_amount > 0
            ORDER BY issued_on, id
            """,
            (tenant_id,),
        ).fetchall()
        return [
            InvoicingCreditNote(row["id"], row["issued_on"], Decimal(row["remaining_amount"]))
            for row in rows
        ]

    def list_credit_notes(self, tenant_id: UUID) -> list[dict]:
        return self.connection.execute(
            """
            SELECT id, issued_on, remaining_amount
            FROM billing_svc.credit_notes
            WHERE tenant_id = %s
            ORDER BY issued_on, id
            """,
            (tenant_id,),
        ).fetchall()

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
        subscription_id: UUID,
        overage: InvoicingOverage,
        rollover_units: int,
        created_on: date,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO billing_svc.rating_results (
                id, period_id, subscription_id, used_units, quota_units, rollover_units,
                billable_units, overage_amount, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, (%s::date)::timestamp AT TIME ZONE 'UTC')
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
                overage.used_units,
                overage.quota_units,
                rollover_units,
                overage.billable_units,
                overage.overage_amount,
                created_on,
            ),
        )

    def upsert_issued_invoice(
        self, invoice_id: UUID, tenant_id: UUID, period_id: UUID, issued_on: date
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO billing_svc.invoices (
                id, tenant_id, period_id, issued_at, subtotal, tax, total, status
            ) VALUES (
                %s, %s, %s, (%s::date)::timestamp AT TIME ZONE 'UTC', 0, 0, 0, 'issued'
            )
            ON CONFLICT (id) DO UPDATE SET status = 'issued'
            """,
            (invoice_id, tenant_id, period_id, issued_on),
        )

    def replace_invoice_lines(
        self, invoice_id: UUID, lines: list[tuple[UUID, InvoiceLineRow]]
    ) -> None:
        self.connection.execute(
            "DELETE FROM billing_svc.invoice_lines WHERE invoice_id = %s", (invoice_id,)
        )
        for line_id, line in lines:
            self.connection.execute(
                """
                INSERT INTO billing_svc.invoice_lines (
                    id, invoice_id, line_no, line_type, description, amount
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (line_id, invoice_id, line.line_no, line.line_type, line.description, line.amount),
            )

    def update_invoice_totals(self, invoice_id: UUID, totals: InvoiceTotals) -> None:
        self.connection.execute(
            """
            UPDATE billing_svc.invoices
               SET subtotal = %s, tax = %s, total = %s
             WHERE id = %s
            """,
            (totals.subtotal, totals.tax, totals.total, invoice_id),
        )

    def update_credit_note_remaining(self, credit_note_id: UUID, remaining: Decimal) -> None:
        self.connection.execute(
            "UPDATE billing_svc.credit_notes SET remaining_amount = %s WHERE id = %s",
            (remaining, credit_note_id),
        )

    def invoice_state(self, period_id: UUID) -> list[dict]:
        return self.connection.execute(
            """
            SELECT status, subtotal, tax, total
            FROM billing_svc.invoices
            WHERE period_id = %s
            """,
            (period_id,),
        ).fetchall()

    def list_invoice_lines(self, invoice_id: UUID) -> list[InvoiceLineRow]:
        rows = self.connection.execute(
            """
            SELECT line_no, line_type, description, amount
            FROM billing_svc.invoice_lines
            WHERE invoice_id = %s
            ORDER BY line_no
            """,
            (invoice_id,),
        ).fetchall()
        return [
            InvoiceLineRow(
                row["line_no"], row["line_type"], row["description"], Decimal(row["amount"])
            )
            for row in rows
        ]
