import json
import os
from decimal import Decimal

import pytest
from warehouse_clients import ROOT, ContractConnection, EmulatorWarehouse, SnowflakeWarehouse

from finance_warehouse import COLUMNS, TeradataReceivablesWarehouse


def test_ar_aging_contract():
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
    rows = TeradataReceivablesWarehouse(connect=lambda **kwargs: connection).ar_aging()
    expected = json.loads((ROOT / "expected/ar-aging.json").read_text())
    assert connection.result["query"] == expected["query"]
    assert connection.result["columns"] == list(COLUMNS)
    assert len(rows) == expected["row_count"]
    assert [row["ACCOUNT_NO"] for row in rows] == expected["keys"]
    for column, total in expected["sums"].items():
        assert sum((Decimal(row[column]) for row in rows), Decimal(0)) == Decimal(total)
    for row in rows:
        assert sum(Decimal(row[column]) for column in (
            "CURRENT_AMT", "DAYS_1_30", "DAYS_31_60", "DAYS_61_90", "DAYS_OVER_90",
        )) == Decimal(row["OPEN_BALANCE"])
