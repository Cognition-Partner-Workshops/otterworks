from __future__ import annotations

import importlib
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE.parent / "consumers")]
report_parity = importlib.import_module("report_parity")
report_catalog = importlib.import_module("report_catalog")


def definitions():
    return {
        d.name: d
        for d in report_parity.load_definitions(HERE / "reports.yaml", report_parity.REPORTS_DIR)
    }


def test_every_report_has_a_manifest_entry_and_a_view():
    found = definitions()
    assert len(found) == 30
    views = HERE.parent / "target" / "dbt" / "models" / "reports"
    assert sorted(found) == sorted(path.stem for path in views.glob("rpt_*.sql"))


def test_queries_bind_the_same_parameter_values_on_both_sides():
    report = definitions()["rpt_plan_tier_summary"]
    values = report_parity.parameter_values(report, date(2026, 9, 30))
    source_sql, source_args = report_parity.sqlserver_query(report, values)
    target_sql, target_args = report_parity.snowflake_query(
        report, "OW_UBW_SFM_20261013_LV", values
    )
    assert "@" not in source_sql and source_sql.count("%s") == 2
    assert source_args == target_args == (date(2026, 9, 30), "Growth")
    assert '"REPORTS"."RPT_PLAN_TIER_SUMMARY"' in target_sql
    assert '"PLAN_TIER" = %s' in target_sql


def test_excluded_columns_are_not_compared():
    report = definitions()["rpt_capacity_forecast"]
    assert "forecast_generated_at" not in report.compared
    assert "forecast_bytes_30d" in report.compared


def test_multiset_comparison_matches_rows_regardless_of_order_and_type():
    columns = ["tenant_id", "units", "event_ts_utc"]
    ts = datetime(2026, 9, 30, 1, 2, 3)
    source = pd.DataFrame([["a", 1, ts], ["a", 1, ts], ["b", 2, ts]], columns=columns)
    target = pd.DataFrame(
        [["b", Decimal("2"), ts], ["a", Decimal("1.0"), ts], ["a", 1, ts]],
        columns=[c.upper() for c in columns],
    )
    assert report_parity.compare_multiset(source, target, columns).status == "PASS"
    target = target.iloc[:2]
    result = report_parity.compare_multiset(source, target, columns)
    assert result.status == "DIVERGE"
    assert result.differences[0]["sqlserver"] == "2 rows"


def test_report_service_catalog_is_in_sync_with_the_report_definitions():
    expected = report_catalog.render(report_catalog.build_catalog())
    assert report_catalog.CATALOG.read_text(encoding="utf-8") == expected
