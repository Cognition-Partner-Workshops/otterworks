"""OW_BILLING estate taken out of Oracle into PostgreSQL 15.

Schema and package ports live in services/legacy-billing/db/postgres/initdb/
(own container: docker-compose.billing-postgres.yml). This module offers the
same functions as backends/oracle.py, and renders values the way oracledb
with fetch_decimals does, so the HTTP surface is unchanged: NUMBER values come
back as canonical decimal strings ("49", not "49.00"), midnight DATEs as
ISO dates.
"""
import os
from datetime import date, datetime, time
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

import psycopg
from psycopg import errors

from . import UsageRejected

NAME = "ow_billing_pg"
FACADE = True
Error = psycopg.Error
UNAVAILABLE_DETAIL = "the PostgreSQL billing estate is not reachable"
USAGE_RULE_SQLSTATES = ("OW001", "OW002")


def connect():
    return psycopg.connect(
        host=os.getenv("BILLING_PG_HOST", "localhost"),
        port=int(os.getenv("BILLING_PG_PORT", "55433")),
        dbname=os.getenv("BILLING_PG_DB", "ow_tp_billing"),
        user=os.getenv("BILLING_PG_USER", "ow_billing"),
        password=os.getenv("BILLING_PG_PASSWORD", "ow_billing"),
        options="-c search_path=ow_billing,public -c TimeZone=UTC",
        connect_timeout=5,
    )


def oracle_number(value):
    if isinstance(value, int):
        return str(value)
    value = value.normalize()
    return "0" if value.is_zero() else format(value, "f")


def _json_value(value):
    if isinstance(value, datetime):
        if value.time() == time.min:
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, Decimal)):
        return oracle_number(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def rows(cursor):
    names = [column.name for column in cursor.description]
    return [
        {name: _json_value(value) for name, value in zip(names, row)}
        for row in cursor
    ]


def query(sql, params=()):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        return rows(cursor)


def report_query(sql, params):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def _function(name, args=()):
    placeholders = ", ".join(["%s"] * len(args))
    return query(f"SELECT * FROM {name}({placeholders})", args)


def _procedure(name, args=()):
    placeholders = ", ".join(["%s"] * len(args))
    with connect() as connection:
        connection.execute(f"CALL {name}({placeholders})", args)


def health():
    query("SELECT 1")


def list_plans():
    return _function("pkg_plans.fn_list_plans")


def entitlement(tenant_id, on):
    return _function("pkg_plans.fn_entitlement", (tenant_id, _as_date(on)))


def change_plan(tenant_id, plan_id, effective_on):
    effective_date = _as_date(effective_on)
    with connect() as connection:
        connection.execute(
            """UPDATE subscriptions
               SET ends_on = %(eff)s::date - 1,
                   status_cd = CASE WHEN status_cd = 30 THEN 30 ELSE 10 END
             WHERE tenant_id = %(t)s
               AND ends_on IS NULL
               AND starts_on = %(eff)s""",
            {"eff": effective_date, "t": tenant_id},
        )
        connection.execute(
            "CALL pkg_plans.sp_change_plan(%s, %s, %s)",
            (tenant_id, plan_id, effective_date),
        )


def usage_rating(tenant, start, end):
    return _function("pkg_rating.fn_usage_rating", (tenant, _as_date(start), _as_date(end)))


def usage_summary(tenant, start, end):
    return _function("pkg_rating.fn_usage_summary", (tenant, _as_date(start), _as_date(end)))


def finalize_rating(tenant, start, end):
    _procedure("pkg_rating.sp_finalize_rating", (tenant, _as_date(start), _as_date(end)))


def invoice_preview(tenant, start, end):
    return _function("pkg_invoicing.fn_invoice_preview", (tenant, _as_date(start), _as_date(end)))


def issue_invoice(tenant, start, end):
    _procedure("pkg_invoicing.sp_issue_invoice", (tenant, _as_date(start), _as_date(end)))


def invoice_lines(invoice_id):
    return _function("pkg_invoicing.fn_invoice_lines", (invoice_id,))


def overdue(as_of):
    return _function("pkg_dunning.fn_overdue_accounts", (_as_date(as_of),))


def schedule_dunning(as_of):
    _procedure("pkg_dunning.sp_schedule_dunning", (_as_date(as_of),))


def suspend_overdue(as_of):
    _procedure("pkg_dunning.sp_suspend_overdue", (_as_date(as_of),))


def ensure_tenant(connection, tenant_id, email):
    if connection.execute("SELECT 1 FROM tenants WHERE id = %s", (tenant_id,)).fetchone():
        return False
    try:
        connection.execute(
            """INSERT INTO tenants (id, name, tax_exempt_yn, status_cd)
               VALUES (%s, %s, 'N', 10)""",
            (tenant_id, email or tenant_id),
        )
    except psycopg.IntegrityError:
        connection.rollback()
        return False
    plan = connection.execute(
        """SELECT id FROM plans
            WHERE COALESCE(active_yn, 'N') = 'Y'
            ORDER BY monthly_fee, id
            LIMIT 1"""
    ).fetchone()
    if not plan:
        raise RuntimeError("no active billing plan")
    subscription_id = str(uuid5(NAMESPACE_URL, f"ow:{tenant_id}:sub"))
    try:
        connection.execute(
            """INSERT INTO subscriptions
               (id, tenant_id, plan_id, starts_on, status_cd)
               VALUES (%s, %s, %s, CURRENT_DATE, 10)""",
            (subscription_id, tenant_id, plan[0]),
        )
    except psycopg.IntegrityError:
        connection.rollback()
        return False
    connection.commit()
    return True


def ensure(tenant_id, email):
    with connect() as connection:
        ensure_tenant(connection, tenant_id, email)


def tenant_profile(tenant_id):
    return query(
        """SELECT t.id AS tenant_id, t.name,
                  ts.code_desc AS status, t.tax_exempt_yn AS tax_exempt
             FROM tenants t
             LEFT JOIN codes ts
               ON ts.code_type = 'TENANT_STATUS'
              AND ts.code_val = t.status_cd
            WHERE t.id = %s""",
        (tenant_id,),
    )


def customer_summary(tenant_id):
    return query(
        """SELECT cust_no, cust_name, cur_bal_amt, past_due_amt, credit_hold_yn
             FROM customer_master
            WHERE tenant_id = %s
            ORDER BY cust_seq_no
            LIMIT 1""",
        (tenant_id,),
    )


def usage_events(tenant_id, start, end):
    return query(
        """SELECT u.id, u.occurred_at, u.units, c.code_desc AS kind
             FROM usage_events u
             JOIN codes c
               ON c.code_type = 'USAGE_KIND'
              AND c.code_val = u.kind_cd
            WHERE u.tenant_id = %s
              AND u.occurred_at >= %s
              AND u.occurred_at < %s::date + 1
            ORDER BY u.occurred_at DESC, u.id DESC
            LIMIT 50""",
        (tenant_id, _as_date(start), _as_date(end)),
    )


def tenant_invoices(tenant_id):
    return query(
        """SELECT i.id AS invoice_id, rp.period_start, rp.period_end,
                  i.subtotal, i.tax, i.total, c.code_desc AS status
             FROM invoices i
             JOIN rating_periods rp ON rp.id = i.period_id
             LEFT JOIN codes c
               ON c.code_type = 'INV_STATUS'
              AND c.code_val = i.status_cd
            WHERE i.tenant_id = %s
            ORDER BY i.issued_at DESC, i.id DESC""",
        (tenant_id,),
    )


def invoice_owned(invoice_id, tenant_id):
    return bool(query(
        "SELECT 1 FROM invoices WHERE id = %s AND tenant_id = %s",
        (invoice_id, tenant_id),
    ))


def customer_record(tenant_id):
    return query(
        "SELECT * FROM customer_master WHERE tenant_id = %s ORDER BY cust_seq_no LIMIT 1",
        (tenant_id,),
    )


def customer_attributes(cust_id):
    return query(
        """SELECT * FROM entity_attr_value
            WHERE entity_type = 'CUSTOMER' AND entity_id = %s
            ORDER BY eav_id""",
        (cust_id,),
    )


def dunning_attempts(as_of):
    return query(
        """SELECT d.id, d.tenant_id, d.invoice_id, d.attempt_no,
                  d.scheduled_for, c.code_desc AS status
             FROM dunning_attempts d
             LEFT JOIN codes c
               ON c.code_type = 'DUN_STATUS'
              AND c.code_val = d.status_cd
            WHERE d.scheduled_for <= %s
            ORDER BY d.scheduled_for DESC, d.id DESC
            LIMIT 200""",
        (_as_date(as_of),),
    )


def ingest_usage_event(tenant_id, email, event_id, kind, units, occurred_at):
    """Insert one usage event; returns "recorded" or "duplicate"."""
    with connect() as connection:
        ensure_tenant(connection, tenant_id, email)
        try:
            kind_row = connection.execute(
                """SELECT code_val FROM codes
                    WHERE code_type = 'USAGE_KIND'
                      AND LOWER(code_desc) = LOWER(%s)""",
                (kind,),
            ).fetchone()
            connection.execute(
                """INSERT INTO usage_events
                   (id, tenant_id, occurred_at, units, kind_cd)
                   VALUES (%s, %s, %s, %s, %s)""",
                (event_id, tenant_id, _as_datetime(occurred_at), units,
                 kind_row[0] if kind_row else None),
            )
        except errors.UniqueViolation:
            connection.rollback()
            return "duplicate"
        except psycopg.Error as exc:
            if exc.sqlstate in USAGE_RULE_SQLSTATES:
                connection.rollback()
                raise UsageRejected(str(exc)) from exc
            raise
    return "recorded"


def _as_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
