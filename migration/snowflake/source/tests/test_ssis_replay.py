from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from source.replay.ssis_replay import evaluate_expression, parse_package

SNOWFLAKE_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_TABLES = {
    "pkg_billing_core": {
        "stg_billing_tenants",
        "stg_billing_plans",
        "stg_billing_subscriptions",
    },
    "pkg_billing_usage": {"stg_billing_usage_events"},
    "pkg_billing_invoices": {"stg_billing_invoices"},
    "pkg_auth_users": {"stg_auth_users"},
    "pkg_auth_memberships": {"stg_auth_workspace_members"},
    "pkg_documents": {"stg_documents"},
    "pkg_document_versions": {"stg_document_versions"},
    "pkg_files": {"stg_files"},
    "pkg_file_versions": {"stg_file_versions"},
    "pkg_collaboration": {"stg_collab_events"},
    "pkg_audit": {"stg_audit_events"},
    "pkg_analytics": {"stg_analytics_events"},
}
SCRIPT_INTENTS = {
    "pkg_billing_usage": "watermark_read",
    "pkg_files": "unit_conversion",
    "pkg_analytics": "checksum",
}


@pytest.mark.parametrize(("package_name", "tables"), PACKAGE_TABLES.items())
def test_packages_parse_and_target_expected_staging_tables(
    package_name: str, tables: set[str]
) -> None:
    package = parse_package(SNOWFLAKE_ROOT / "source" / "ssis" / f"{package_name}.dtsx")
    flows = [task.data_flow for task in package.executables if task.data_flow is not None]

    assert package.name == package_name
    assert {flow.destination_table.split(".")[-1].strip("[]") for flow in flows} == tables
    for data_flow in flows:
        component_types = {component.component_type for component in data_flow.components}
        assert "FlatFileSource" in component_types
        assert "OLEDBDestination" in component_types
        assert component_types.intersection({"DerivedColumn", "Lookup"})


def test_script_tasks_have_replay_intents_and_bodies() -> None:
    for package_name, expected_intent in SCRIPT_INTENTS.items():
        package = parse_package(SNOWFLAKE_ROOT / "source" / "ssis" / f"{package_name}.dtsx")
        script_tasks = [
            task for task in package.executables if task.executable_type == "Microsoft.ScriptTask"
        ]

        assert len(script_tasks) == 1
        assert script_tasks[0].script_intent == expected_intent
        assert script_tasks[0].script_body.strip()


def test_expression_evaluator_handles_source_transformations() -> None:
    row = {
        "archived": None,
        "email": "writer@sample.invalid",
        "occurred_at": 1_790_000_000_123_456_789,
        "overage_rate": "0.250000",
        "created_at": "2026-09-01T03:04:05.123456Z",
    }

    assert evaluate_expression(
        'ISNULL(archived) ? NULL(DT_BOOL) : (DT_BOOL)(archived == "t")', row
    ) is None
    assert evaluate_expression(
        'LOWER(SUBSTRING(email, FINDSTRING(email,"@",1)+1, 255))', row
    ) == "sample.invalid"
    assert evaluate_expression("(DT_I4)ROUND(overage_rate * 100, 0)", row) == 25
    assert evaluate_expression(
        '(DT_DBTIMESTAMP2,7)REPLACE(REPLACE(created_at,"T"," "),"Z","")', row
    ) == datetime(2026, 9, 1, 3, 4, 5, 123456)
    assert evaluate_expression(
        'DATEADD("ss",(DT_I4)(occurred_at / 1000000000),'
        '(DT_DBTIMESTAMP2,7)"1970-01-01 00:00:00")',
        row,
    ) == datetime(1970, 1, 1) + timedelta(seconds=1_790_000_000)
