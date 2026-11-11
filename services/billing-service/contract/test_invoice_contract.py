from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal

import pytest
from input_parity import input_equality
from warehouse_clients import (
    ROOT,
    ContractConnection,
    EmulatorWarehouse,
    SnowflakeWarehouse,
)

from app.export_invoices import export_invoices
from app.warehouse.databricks import REQUIRED_ENV, DatabricksInvoiceWarehouse
from app.warehouse.teradata import TeradataInvoiceWarehouse


def test_invoice_export_contract(monkeypatch, tmp_path):
    target = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    live_warehouse = None
    if target == "databricks":
        if not all(os.getenv(key) for key in REQUIRED_ENV):
            pytest.skip("Databricks environment not configured: " + ", ".join(REQUIRED_ENV))
        inputs = input_equality()
        print("input equality:", json.dumps(inputs, sort_keys=True))
        live_warehouse = DatabricksInvoiceWarehouse()
        live_rows = live_warehouse.invoices_for_run(date(2026, 11, 10))
        print("Databricks statement_id:", live_warehouse.last_result["statement_id"])
        monkeypatch.setenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
        adapter = EmulatorWarehouse()
    elif target in {"teradata-emulator", "replay", "snowflake-semantics"}:
        adapter = EmulatorWarehouse()
    elif target == "snowflake":
        required = ("ACCOUNT", "USER", "ROLE", "WAREHOUSE", "PRIVATE_KEY")
        if not all(os.getenv(f"SNOWFLAKE_{key}") for key in required):
            pytest.skip("Snowflake environment not configured")
        adapter = SnowflakeWarehouse()
    else:
        pytest.fail(f"unknown WAREHOUSE_CONTRACT_TARGET: {target}")
    connection = ContractConnection(adapter)
    warehouse = TeradataInvoiceWarehouse(connect=lambda **kwargs: connection)
    rows = warehouse.invoices_for_run(date(2026, 11, 10))
    if live_warehouse:
        assert live_warehouse.last_result["columns"] == connection.result["columns"]
        assert live_rows == rows

        class ResultWarehouse:
            def __init__(self, values):
                self.values = values

            def invoices_for_run(self, _run_date):
                return self.values

        for name, values in (("old", rows), ("databricks", live_rows)):
            export_invoices(ResultWarehouse(values), date(2026, 11, 10), tmp_path / (name + ".csv"))
        assert (tmp_path / "old.csv").read_bytes() == (tmp_path / "databricks.csv").read_bytes()
        print(f"old path == Databricks: {len(rows)} rows; all fields equal; run_date=2026-11-10")
    expected = json.loads((ROOT / "expected/invoice-export.json").read_text())
    assert connection.parameters == ["2026-11-10"]
    assert connection.result["query"] == expected["query"]
    assert len(rows) == expected["row_count"]
    assert [row.invoice_no for row in rows] == expected["keys"]
    attributes = {"AMOUNT_DUE": "amount_due", "TAX_AMT": "tax_amt", "OPEN_BALANCE": "open_balance"}
    for column, total in expected["sums"].items():
        assert sum((getattr(row, attributes[column]) for row in rows), Decimal(0)) == Decimal(total)
