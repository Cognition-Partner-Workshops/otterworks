from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.warehouse.databricks import SQL, DatabricksInvoiceWarehouse, execute
from app.warehouse.teradata import WarehouseSettings


@pytest.mark.parametrize("run_date,parameter", [(date(2026, 11, 10), "2026-11-10"), (None, None)])
def test_native_dal_maps_rows_and_binds_date(run_date, parameter):
    transport = MagicMock(
        return_value={
            "statement_id": "unit-query",
            "rows": [
                [
                    "INV-1",
                    "Generic account ",
                    "A1 ",
                    date(2026, 11, 9),
                    "USD ",
                    Decimal("12.30"),
                    Decimal("1.20"),
                    Decimal("0.00"),
                ]
            ],
        }
    )
    warehouse = DatabricksInvoiceWarehouse(transport=transport)
    (row,) = warehouse.invoices_for_run(run_date)
    transport.assert_called_once_with(SQL, [parameter], step="contract-fixed")
    assert row.customer_name == "Generic account "
    assert row.account_no == "A1"
    assert row.currency_cd == "USD"
    assert str(row.amount_due) == "12.30"
    assert row.open_balance == Decimal("0.00")
    assert warehouse.last_result["statement_id"] == "unit-query"


def test_native_dal_disabled_empty_and_overflow():
    transport = MagicMock(return_value={"rows": []})
    warehouse = DatabricksInvoiceWarehouse(WarehouseSettings(enabled=False), transport)
    with pytest.raises(RuntimeError, match="disabled"):
        warehouse.invoices_for_run(None)
    transport.assert_not_called()
    warehouse = DatabricksInvoiceWarehouse(transport=transport)
    assert warehouse.invoices_for_run(None) == []
    transport.return_value = {"rows": [None] * 100001}
    with pytest.raises(RuntimeError, match="exceeds"):
        warehouse.invoices_for_run(None)


def test_connector_tags_query_and_returns_statement_id(monkeypatch):
    from databricks import sql

    connect = MagicMock()
    monkeypatch.setattr(sql, "connect", connect)
    monkeypatch.setenv("DATABRICKS_HOST", "https://unit.databricks.com/")
    monkeypatch.setenv("DATABRICKS_TOKEN", "unit-only-not-a-credential")
    monkeypatch.setenv("DATABRICKS_WAREHOUSE_ID", "012abc")
    monkeypatch.setenv("DATABRICKS_CATALOG", "cpw")
    monkeypatch.setenv("DATABRICKS_RUN_TOKEN", "dbx-d1111")
    cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.description = [("value",)]
    cursor.fetchall.return_value = [(1,)]
    cursor.query_id = "unit-query"
    assert execute("SELECT ? AS value", [1], step="contract-fixed") == {
        "columns": ["VALUE"],
        "rows": [[1]],
        "statement_id": "unit-query",
    }
    cursor.execute.assert_called_once_with(
        "/* run=dbx-d1111 act=consumers step=contract-fixed consumer=billing-service */\n"
        "SELECT ? AS value",
        [1],
    )
    assert connect.call_args.kwargs["catalog"] == "cpw"
    assert connect.call_args.kwargs["schema"] == "dbx_d1111_after"
    assert connect.return_value.__exit__.called
    cursor.execute.side_effect = RuntimeError("query failed")
    with pytest.raises(RuntimeError, match="query failed"):
        execute("SELECT 1")
    assert connect.return_value.__enter__.return_value.cursor.return_value.__exit__.called
    monkeypatch.setenv("DATABRICKS_RUN_TOKEN", "another-run")
    with pytest.raises(ValueError, match="restricted"):
        execute("SELECT 1")


def test_cli_defaults_to_databricks(tmp_path, monkeypatch):
    import app.export_invoices as module

    monkeypatch.delenv("FINANCE_WAREHOUSE_TARGET", raising=False)
    warehouse = MagicMock()
    warehouse.invoices_for_run.return_value = []
    factory = MagicMock(return_value=warehouse)
    monkeypatch.setattr(module, "DatabricksInvoiceWarehouse", factory)
    assert module.main(["--date", "2026-11-10", "--out", str(tmp_path / "empty.csv")]) == 0
    factory.assert_called_once()
    warehouse.invoices_for_run.assert_called_once_with(date(2026, 11, 10))
