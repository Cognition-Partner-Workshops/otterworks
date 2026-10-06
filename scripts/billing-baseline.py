#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]==3.2.9"]
# ///
"""Snapshot billing row counts and billing.fn_usage_summary as markdown.

Captures the numbers later migration phases compare against:

1. the row count of every table in the ``billing`` schema and in the
   ``billing_svc`` schema the billing service uses;
2. ``billing.fn_usage_summary`` (kind, event_count, units) for every tenant in
   each requested period, plus grand totals per period.

Connections (rerunnable against the local procs stack or the RDS database):

- billing schema: ``--legacy-url`` / ``LEGACY_BILLING_DATABASE_URL``, otherwise
  ``DB_HOST``/``DB_PORT``/``DB_NAME``/``DB_USER``/``DB_PASSWORD`` (same
  variables and defaults as ``procs/harness/record.py``).
- billing_svc schema: ``--billing-svc-url`` / ``BILLING_SVC_DATABASE_URL``,
  otherwise the billing-schema connection (single-database layout, as on RDS).

Usage:
    uv run scripts/billing-baseline.py [--period 2026-02-01:2026-02-28 ...] [--output FILE]
    make procs-baseline NS=<ns>
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone

import psycopg
from psycopg import sql

DEFAULT_PERIODS = ("2026-02-01:2026-02-28", "2026-09-01:2026-09-30")
LEGACY_TABLES = (
    "tenants", "plans", "subscriptions", "usage_events", "rating_periods",
    "rating_results", "invoices", "invoice_lines", "credit_notes",
    "dunning_attempts", "notifications",
)
BILLING_SVC_TABLES = (
    "tenants", "plans", "subscriptions", "usage_events", "rating_periods",
    "rating_results",
)
KINDS = ("api", "compute", "storage")


def connect(url: str | None) -> psycopg.Connection:
    if url:
        return psycopg.connect(url, connect_timeout=10)
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "55432")),
        dbname=os.getenv("DB_NAME", f"billing_{os.getenv('NS', 'dev')}"),
        user=os.getenv("DB_USER", "billing"),
        password=os.getenv("DB_PASSWORD", "billing"),
        connect_timeout=10,
    )


def describe(conn: psycopg.Connection) -> str:
    info = conn.info
    return f"{info.user}@{info.host}:{info.port}/{info.dbname}"


def parse_period(value: str) -> tuple[date, date]:
    start, _, end = value.partition(":")
    try:
        period = (date.fromisoformat(start), date.fromisoformat(end))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD:YYYY-MM-DD, got {value!r}") from exc
    if period[1] < period[0]:
        raise argparse.ArgumentTypeError(f"period end before start: {value!r}")
    return period


def row_counts(conn: psycopg.Connection, schema: str, expected: tuple[str, ...]) -> list[tuple[str, str]]:
    present = {
        name for (name,) in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE'",
            (schema,),
        )
    }
    rows = []
    for table in list(expected) + sorted(present - set(expected)):
        if table not in present:
            rows.append((table, "missing"))
            continue
        query = sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(table))
        rows.append((table, str(conn.execute(query).fetchone()[0])))  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
    return rows


def usage_summary(conn: psycopg.Connection, start: date, end: date):
    tenants = conn.execute("SELECT id, name FROM billing.tenants ORDER BY id").fetchall()
    per_tenant = []
    for tenant_id, name in tenants:
        rows = conn.execute(
            "SELECT kind, event_count, units FROM billing.fn_usage_summary(%s, %s, %s)",
            (tenant_id, start, end),
        ).fetchall()
        per_tenant.append((tenant_id, name, rows))
    return per_tenant


def render_summary(start: date, end: date, per_tenant) -> list[str]:
    out = [f"### billing.fn_usage_summary {start}..{end}", ""]
    out += ["| tenant_id | tenant | kind | event_count | units |", "| --- | --- | --- | ---: | ---: |"]
    totals = {kind: [0, 0] for kind in KINDS}
    for tenant_id, name, rows in per_tenant:
        if not rows:
            out.append(f"| {tenant_id} | {name} | (no rows) | 0 | 0 |")
        for kind, count, units in rows:
            out.append(f"| {tenant_id} | {name} | {kind} | {count} | {units} |")
            totals.setdefault(kind, [0, 0])
            totals[kind][0] += count
            totals[kind][1] += units
    out += ["", f"Grand totals {start}..{end}:", ""]
    out += ["| kind | event_count | units |", "| --- | ---: | ---: |"]
    for kind, (count, units) in totals.items():
        out.append(f"| {kind} | {count} | {units} |")
    all_count = sum(c for c, _ in totals.values())
    all_units = sum(u for _, u in totals.values())
    out += [f"| **all** | **{all_count}** | **{all_units}** |", ""]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--legacy-url", default=os.getenv("LEGACY_BILLING_DATABASE_URL"))
    parser.add_argument("--billing-svc-url", default=os.getenv("BILLING_SVC_DATABASE_URL"))
    parser.add_argument("--period", action="append", type=parse_period,
                        help="YYYY-MM-DD:YYYY-MM-DD, repeatable (default: Feb 2026 and Sep 2026)")
    parser.add_argument("--output", help="also write the markdown to this file")
    args = parser.parse_args()
    periods = args.period or [parse_period(p) for p in DEFAULT_PERIODS]

    try:
        legacy = connect(args.legacy_url)
        svc = connect(args.billing_svc_url) if args.billing_svc_url else legacy
    except psycopg.OperationalError as exc:
        print(f"billing-baseline: cannot connect: {exc}", file=sys.stderr)
        return 3

    with legacy, svc:
        out = [
            "## Billing baseline",
            "",
            f"Captured {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}; "
            f"billing: `{describe(legacy)}`; billing_svc: `{describe(svc)}`.",
            "",
            "### Row counts",
            "",
            "| schema | table | rows |",
            "| --- | --- | ---: |",
        ]
        for schema, conn, expected in (("billing", legacy, LEGACY_TABLES), ("billing_svc", svc, BILLING_SVC_TABLES)):
            for table, count in row_counts(conn, schema, expected):
                out.append(f"| {schema} | {table} | {count} |")
        out.append("")
        for start, end in periods:
            out += render_summary(start, end, usage_summary(legacy, start, end))

    text = "\n".join(out)
    print(text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
