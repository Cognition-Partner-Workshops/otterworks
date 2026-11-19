from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import psycopg

from app.domain import EntitlementRow, PlanRow, SubscriptionRow


class PostgresPlansRepository:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def lock_tenant(self, tenant_id: UUID) -> None:
        self.connection.execute(
            'SELECT id FROM billing_svc.tenants WHERE id = %s FOR UPDATE', (tenant_id,)
        )

    def invoice_exists(self, invoice_id: UUID) -> bool:
        return self.connection.execute(
            'SELECT id FROM billing_svc.invoices WHERE id = %s', (invoice_id,)
        ).fetchone() is not None

    def delete_pending_subscriptions(self, tenant_id: UUID, on: date) -> None:
        self.connection.execute(
            'DELETE FROM billing_svc.subscriptions WHERE tenant_id = %s AND starts_on > %s',
            (tenant_id, on),
        )

    def reopen_subscription(self, subscription_id: UUID) -> None:
        self.connection.execute(
            'UPDATE billing_svc.subscriptions SET ends_on = NULL WHERE id = %s',
            (subscription_id,),
        )

    def set_subscription_plan(self, subscription_id: UUID, plan_id: UUID) -> None:
        self.connection.execute(
            'UPDATE billing_svc.subscriptions SET plan_id = %s WHERE id = %s',
            (plan_id, subscription_id),
        )

    def insert_invoice(self, invoice: dict) -> None:
        self.connection.execute(
            '''INSERT INTO billing_svc.invoices
               (id, tenant_id, issued_on, period_start, period_end, total, summary)
               VALUES (%s, %s, %s, %s, %s, %s, %s)''',
            tuple(invoice[key] for key in (
                'id', 'tenant_id', 'issued_on', 'period_start', 'period_end', 'total', 'summary'
            )),
        )
        for number, line in enumerate(invoice['lines'], 1):
            self.connection.execute(
                '''INSERT INTO billing_svc.invoice_lines
                   (invoice_id, line_no, description, amount) VALUES (%s, %s, %s, %s)''',
                (invoice['id'], number, line['description'], line['amount']),
            )

    def list_invoices(self, tenant_id: UUID) -> list[dict]:
        rows = self.connection.execute(
            '''SELECT id, tenant_id, issued_on, period_start, period_end, total, summary
               FROM billing_svc.invoices WHERE tenant_id = %s
               ORDER BY issued_on DESC, created_at DESC, id DESC''', (tenant_id,),
        ).fetchall()
        invoices = []
        for row in rows:
            lines = self.connection.execute(
                '''SELECT description, amount FROM billing_svc.invoice_lines
                   WHERE invoice_id = %s ORDER BY line_no''', (row['id'],),
            ).fetchall()
            invoices.append({
                'id': str(row['id']), 'tenant_id': str(row['tenant_id']),
                'issued_on': row['issued_on'].isoformat(),
                'period_start': row['period_start'].isoformat(),
                'period_end': row['period_end'].isoformat(), 'total': f"{row['total']:.2f}",
                'summary': row['summary'],
                'lines': [{'description': line['description'], 'amount': f"{line['amount']:.2f}"}
                          for line in lines],
            })
        return invoices

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
