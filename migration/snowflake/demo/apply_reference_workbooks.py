"""Fallback: write the Snowflake copy of all 20 legacy Tableau workbooks for a run token.

This is the reference output of the Tableau fan-out. Each datasource keeps its caption and
parameters, connects to the run's Snowflake database as the read-only viewer, and reads the
dbt model that replaces its legacy table.
"""

from __future__ import annotations

import argparse
import html
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "source" / "tableau"
TARGET = ROOT / "target" / "tableau"
SEATS = (
    "(SELECT s.business_date, s.tenant_id, s.plan_id, s.plan_tier, s.seat_count, "
    "l.seat_limit, l.over_limit FROM MARTS.ROLLUP_SEATS s JOIN MARTS.APPLY_PLAN_LIMITS l "
    "ON l.business_date = s.business_date AND l.tenant_id = s.tenant_id) fact_seat_assignments"
)
TABLES = {
    "mart.mart_overage_charges": "MARTS.BUILD_MART_OVERAGE",
    "mart.mart_tenant_usage_daily": "MARTS.BUILD_MART_TENANT_USAGE",
    "mart.mart_plan_seat_summary": "MARTS.BUILD_MART_PLAN_SEAT_SUMMARY",
    "mart.mart_retention_summary": "MARTS.BUILD_MART_RETENTION",
    "mart.mart_audit_rollup": "MARTS.BUILD_MART_AUDIT",
    "mart.mart_capacity_forecast_input": "MARTS.BUILD_CAPACITY_FORECAST_INPUT",
    "fact.fact_invoice_lines": "MARTS.BUILD_INVOICE_LINES",
    "fact.fact_audit_events": "MARTS.ROLLUP_AUDIT",
    "fact.fact_retention_actions": "MARTS.ROLLUP_RETENTION",
    "fact.fact_document_status_daily": "MARTS.ROLLUP_DOCUMENT_STATUS",
    "fact.fact_seat_assignments": SEATS,
}


def convert_sql(sql: str) -> str:
    for old, new in TABLES.items():
        sql = sql.replace(old, new)
    sql = sql.replace("COUNT_BIG(*)", "COUNT(*)")
    top = re.match(r"SELECT TOP \((\d+)\) (.*)$", sql, re.S)
    return f"SELECT {top.group(2)} LIMIT {top.group(1)}" if top else sql


def convert(text: str, prefix: str, host: str) -> str:
    text = re.sub(
        r"<connection authentication='sqlserver' class='sqlserver'[^>]*/>",
        f"<connection authentication='Username Password' class='snowflake' dbname='{prefix}' "
        f"odbc-connect-string-extras='' one-time-sql='' schema='MARTS' server='{host}' "
        f"service='{prefix}_READER' username='{prefix}_VIEWER' warehouse='{prefix}_WH' />",
        text,
    )
    text = re.sub(r"caption='[^']*' name='sqlserver\.", f"caption='{host}' name='snowflake.", text)
    text = text.replace("connection='sqlserver.", "connection='snowflake.")
    return re.sub(
        r"(<relation [^>]*type='text'>)(.*?)(</relation>)",
        lambda m: m.group(1) + escape(convert_sql(html.unescape(m.group(2)))) + m.group(3),
        text,
        flags=re.S,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    prefix = "OW_UBW_" + re.sub(r"[^A-Z0-9]", "_", args.run.upper())
    host = (
        os.environ.get("SNOWFLAKE_HOST")
        or f"{os.environ['SNOWFLAKE_ACCOUNT']}.snowflakecomputing.com"
    )
    TARGET.mkdir(parents=True, exist_ok=True)
    for path in sorted(LEGACY.glob("*.twb")):
        (TARGET / path.name).write_text(convert(path.read_text(), prefix, host))
        print(f"wrote target/tableau/{path.name}")


if __name__ == "__main__":
    main()
