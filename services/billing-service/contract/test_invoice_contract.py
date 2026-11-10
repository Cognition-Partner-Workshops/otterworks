from __future__ import annotations

import json
import os
from datetime import date
from decimal import Decimal

import pytest
from warehouse_clients import (
    ROOT,
    ContractConnection,
    EmulatorWarehouse,
    SnowflakeWarehouse,
)

from app.warehouse.teradata import TeradataInvoiceWarehouse


def test_invoice_export_contract():
    target = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    if target == "teradata-emulator":
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
    rows = warehouse.invoices_for_run(date(2026, 1, 6))
    expected = json.loads((ROOT / "expected/invoice-export.json").read_text())
    assert connection.parameters == ["2026-01-06"]
    assert connection.result["query"] == expected["query"]
    assert len(rows) == expected["row_count"]
    assert [row.invoice_no for row in rows] == expected["keys"]
    attributes = {"AMOUNT_DUE": "amount_due", "TAX_AMT": "tax_amt", "OPEN_BALANCE": "open_balance"}
    for column, total in expected["sums"].items():
        assert sum((getattr(row, attributes[column]) for row in rows), Decimal(0)) == Decimal(total)
