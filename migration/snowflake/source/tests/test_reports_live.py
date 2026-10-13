from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pymssql
import pytest

SNOWFLAKE_ROOT = Path(__file__).resolve().parents[2]
RDL_NAMESPACE = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"


def _connect() -> pymssql.Connection:
    return pymssql.connect(
        server=os.environ.get("UBW_SQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("UBW_SQL_PORT", "14333")),
        user=os.environ.get("UBW_SQL_USER", "sa"),
        password=os.environ.get("UBW_SQL_PASSWORD", "OtterUbw_2016dev"),
        database=os.environ.get("UBW_SQL_DATABASE", "OtterWorksUBW"),
        autocommit=True,
    )


def _report_query(path: Path) -> tuple[str, dict[str, str]]:
    root = ET.parse(path).getroot()
    command_text = root.findtext(f".//{{{RDL_NAMESPACE}}}CommandText")
    if not command_text:
        raise AssertionError(f"{path.name} has no dataset query")
    defaults: dict[str, str] = {}
    for parameter in root.findall(f".//{{{RDL_NAMESPACE}}}ReportParameter"):
        name = parameter.get("Name")
        value = parameter.findtext(
            f"{{{RDL_NAMESPACE}}}DefaultValue/{{{RDL_NAMESPACE}}}Values/"
            f"{{{RDL_NAMESPACE}}}Value"
        )
        if name and value:
            defaults[name] = value
    return command_text, defaults


def _execute_report(cursor: pymssql.Cursor, path: Path) -> None:
    query, defaults = _report_query(path)
    for name, value in defaults.items():
        if name == "BusinessDate":
            value = date.fromisoformat(value).isoformat()
        query = query.replace(f"@{name}", "'" + value.replace("'", "''") + "'")
    cursor.execute(query)
    cursor.fetchmany(1)


def test_report_catalog_and_plan_tier_filter() -> None:
    paths = sorted((SNOWFLAKE_ROOT / "source" / "reports").glob("*.rdl"))
    assert len(paths) == 30
    assert all(path.stem.startswith("rpt_") for path in paths)

    report_path = SNOWFLAKE_ROOT / "source" / "reports" / "rpt_plan_tier_summary.rdl"
    query, defaults = _report_query(report_path)
    assert query == (
        "SELECT business_date, plan_tier, tenant_count, seat_count, seat_limit_total, "
        "tenants_over_limit, avg_seats_per_tenant FROM mart.mart_plan_seat_summary "
        "WHERE business_date = @BusinessDate AND plan_tier = @PlanTier ORDER BY plan_tier"
    )
    assert defaults == {"BusinessDate": "2026-09-30", "PlanTier": "Growth"}
    root = ET.parse(report_path).getroot()
    tier_parameter = root.find(f".//{{{RDL_NAMESPACE}}}ReportParameter[@Name='PlanTier']")
    assert tier_parameter is not None
    values = tier_parameter.findall(
        f".//{{{RDL_NAMESPACE}}}ParameterValue"
    )
    assert [(item.findtext(f"{{{RDL_NAMESPACE}}}Label"), item.findtext(f"{{{RDL_NAMESPACE}}}Value"))
            for item in values] == [
        ("Starter", "Starter"),
        ("Growth", "Growth"),
        ("Scale", "Scale"),
    ]


def test_reports_run_with_default_parameters() -> None:
    try:
        connection = _connect()
    except Exception as error:
        pytest.skip(f"SQL Server is not reachable: {error}")
    try:
        cursor = connection.cursor()
        for path in sorted((SNOWFLAKE_ROOT / "source" / "reports").glob("*.rdl")):
            _execute_report(cursor, path)
        cursor.close()
    finally:
        connection.close()
