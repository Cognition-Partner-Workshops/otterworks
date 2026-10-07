from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg

from app.domain import (
    CreditNoteRow,
    EntitlementRow,
    InvoiceLineRow,
    InvoiceRow,
    InvoiceTotals,
    PlanRow,
    RatingHistoryRow,
    RatingPeriodRow,
    RatingResultRow,
    SubscriptionRow,
    UsageEventRow,
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


class PostgresRatingRepository(PostgresPlansRepository):
    def list_usage_events(self, tenant_id: UUID) -> list[UsageEventRow]:
        rows = self.connection.execute(
            """
            SELECT tenant_id, occurred_at, units, kind
            FROM billing_svc.usage_events
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        ).fetchall()
        return [
            UsageEventRow(
                tenant_id=row["tenant_id"],
                occurred_at=row["occurred_at"],
                units=row["units"],
                kind=row["kind"],
            )
            for row in rows
        ]

    def list_rating_history(self, tenant_id: UUID) -> list[RatingHistoryRow]:
        rows = self.connection.execute(
            """
            SELECT rp.period_start, rr.rollover_units
            FROM billing_svc.rating_results rr
            JOIN billing_svc.rating_periods rp ON rp.id = rr.period_id
            WHERE rp.tenant_id = %s
            """,
            (tenant_id,),
        ).fetchall()
        return [
            RatingHistoryRow(period_start=row["period_start"], rollover_units=row["rollover_units"])
            for row in rows
        ]

    def find_rating_period(self, tenant_id: UUID, period_start: date) -> RatingPeriodRow | None:
        row = self.connection.execute(
            """
            SELECT id, tenant_id, period_start, period_end
            FROM billing_svc.rating_periods
            WHERE tenant_id = %s AND period_start = %s
            """,
            (tenant_id, period_start),
        ).fetchone()
        if row is None:
            return None
        return RatingPeriodRow(
            period_id=row["id"],
            tenant_id=row["tenant_id"],
            period_start=row["period_start"],
            period_end=row["period_end"],
        )

    def insert_rating_period(self, period: RatingPeriodRow) -> None:
        self.connection.execute(
            """
            INSERT INTO billing_svc.rating_periods (id, tenant_id, period_start, period_end)
            VALUES (%s, %s, %s, %s)
            """,
            (period.period_id, period.tenant_id, period.period_start, period.period_end),
        )

    def update_rating_period_end(self, period_id: UUID, period_end: date) -> None:
        self.connection.execute(
            "UPDATE billing_svc.rating_periods SET period_end = %s WHERE id = %s",
            (period_end, period_id),
        )

    def find_rating_result(self, result_id: UUID) -> RatingResultRow | None:
        row = self.connection.execute(
            """
            SELECT id, period_id, subscription_id, used_units, quota_units, rollover_units,
                   billable_units, overage_amount, created_at
            FROM billing_svc.rating_results
            WHERE id = %s
            """,
            (result_id,),
        ).fetchone()
        return None if row is None else _result_row(row)

    def insert_rating_result(self, result: RatingResultRow) -> None:
        self.connection.execute(
            """
            INSERT INTO billing_svc.rating_results (
                id, period_id, subscription_id, used_units, quota_units, rollover_units,
                billable_units, overage_amount, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                result.result_id,
                result.period_id,
                result.subscription_id,
                result.used_units,
                result.quota_units,
                result.rollover_units,
                result.billable_units,
                result.overage_amount,
                result.created_at,
            ),
        )

    def update_rating_result(self, result: RatingResultRow) -> None:
        self.connection.execute(
            """
            UPDATE billing_svc.rating_results
            SET used_units = %s, rollover_units = %s, billable_units = %s, overage_amount = %s
            WHERE id = %s
            """,
            (
                result.used_units,
                result.rollover_units,
                result.billable_units,
                result.overage_amount,
                result.result_id,
            ),
        )

    def list_rating_results(self, tenant_id: UUID, period_start: date) -> list[RatingResultRow]:
        rows = self.connection.execute(
            """
            SELECT id, period_id, subscription_id, used_units, quota_units, rollover_units,
                   billable_units, overage_amount, created_at
            FROM billing_svc.rating_results
            WHERE period_id IN (
                SELECT id FROM billing_svc.rating_periods
                WHERE tenant_id = %s AND period_start = %s
            )
            ORDER BY id
            """,
            (tenant_id, period_start),
        ).fetchall()
        return [_result_row(row) for row in rows]



class PostgresInvoicingRepository(PostgresRatingRepository):
    def find_tax_exempt(self, tenant_id: UUID) -> bool | None:
        row = self.connection.execute(
            "SELECT tax_exempt FROM billing_svc.tenants WHERE id = %s",
            (tenant_id,),
        ).fetchone()
        return None if row is None else row["tax_exempt"]

    def list_credit_notes(self, tenant_id: UUID) -> list[CreditNoteRow]:
        rows = self.connection.execute(
            """
            SELECT id, tenant_id, issued_on, amount, remaining_amount
            FROM billing_svc.credit_notes
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        ).fetchall()
        return [self._credit_note(row) for row in rows]

    def lock_credit_notes(self, tenant_id: UUID) -> list[CreditNoteRow]:
        rows = self.connection.execute(
            """
            SELECT id, tenant_id, issued_on, amount, remaining_amount
            FROM billing_svc.credit_notes
            WHERE tenant_id = %s
            FOR UPDATE
            """,
            (tenant_id,),
        ).fetchall()
        return [self._credit_note(row) for row in rows]

    @staticmethod
    def _credit_note(row: dict) -> CreditNoteRow:
        return CreditNoteRow(
            credit_id=row["id"],
            tenant_id=row["tenant_id"],
            issued_on=row["issued_on"],
            amount=Decimal(row["amount"]),
            remaining_amount=Decimal(row["remaining_amount"]),
        )

    def update_credit_remaining(self, credit_id: UUID, remaining_amount: Decimal) -> None:
        self.connection.execute(
            "UPDATE billing_svc.credit_notes SET remaining_amount = %s WHERE id = %s",
            (remaining_amount, credit_id),
        )

    def find_invoice(self, invoice_id: UUID) -> InvoiceRow | None:
        row = self.connection.execute(
            """
            SELECT id, tenant_id, period_id, issued_at, subtotal, tax, total, status
            FROM billing_svc.invoices
            WHERE id = %s
            """,
            (invoice_id,),
        ).fetchone()
        return None if row is None else _invoice_row(row)

    def list_period_invoices(self, period_id: UUID) -> list[InvoiceRow]:
        rows = self.connection.execute(
            """
            SELECT id, tenant_id, period_id, issued_at, subtotal, tax, total, status
            FROM billing_svc.invoices
            WHERE period_id = %s
            """,
            (period_id,),
        ).fetchall()
        return [_invoice_row(row) for row in rows]

    def insert_invoice(self, invoice: InvoiceRow) -> None:
        self.connection.execute(
            """
            INSERT INTO billing_svc.invoices
                (id, tenant_id, period_id, issued_at, subtotal, tax, total, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                invoice.invoice_id,
                invoice.tenant_id,
                invoice.period_id,
                invoice.issued_at,
                invoice.subtotal,
                invoice.tax,
                invoice.total,
                invoice.status,
            ),
        )

    def update_invoice_status(self, invoice_id: UUID, status: str) -> None:
        self.connection.execute(
            "UPDATE billing_svc.invoices SET status = %s WHERE id = %s",
            (status, invoice_id),
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

    def delete_invoice_lines(self, invoice_id: UUID) -> None:
        self.connection.execute(
            "DELETE FROM billing_svc.invoice_lines WHERE invoice_id = %s",
            (invoice_id,),
        )

    def insert_invoice_line(self, line: InvoiceLineRow) -> None:
        self.connection.execute(
            """
            INSERT INTO billing_svc.invoice_lines
                (id, invoice_id, line_no, line_type, description, amount)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                line.line_id,
                line.invoice_id,
                line.line_no,
                line.line_type,
                line.description,
                line.amount,
            ),
        )

    def list_invoice_lines(self, invoice_id: UUID) -> list[InvoiceLineRow]:
        rows = self.connection.execute(
            """
            SELECT id, invoice_id, line_no, line_type, description, amount
            FROM billing_svc.invoice_lines
            WHERE invoice_id = %s
            """,
            (invoice_id,),
        ).fetchall()
        return [
            InvoiceLineRow(
                line_id=row["id"],
                invoice_id=row["invoice_id"],
                line_no=row["line_no"],
                line_type=row["line_type"],
                description=row["description"],
                amount=Decimal(row["amount"]),
            )
            for row in rows
        ]


def _invoice_row(row: dict) -> InvoiceRow:
    return InvoiceRow(
        invoice_id=row["id"],
        tenant_id=row["tenant_id"],
        period_id=row["period_id"],
        issued_at=row["issued_at"],
        subtotal=Decimal(row["subtotal"]),
        tax=Decimal(row["tax"]),
        total=Decimal(row["total"]),
        status=row["status"],
    )

def _result_row(row: dict) -> RatingResultRow:
    return RatingResultRow(
        result_id=row["id"],
        period_id=row["period_id"],
        subscription_id=row["subscription_id"],
        used_units=row["used_units"],
        quota_units=row["quota_units"],
        rollover_units=row["rollover_units"],
        billable_units=row["billable_units"],
        overage_amount=Decimal(row["overage_amount"]),
        created_at=row["created_at"],
    )
