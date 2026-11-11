import json
import os
from datetime import date
from decimal import Decimal

import pytest
from warehouse_clients import ROOT, ContractConnection, EmulatorWarehouse

from finance_warehouse import COLUMNS, SnowflakeReceivablesWarehouse
from legacy_teradata import LegacyReceivablesWarehouse


def test_ar_aging_contract():
    target = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    if target in {"teradata-emulator", "replay", "snowflake-semantics"}:
        adapter = EmulatorWarehouse()
    elif target == "snowflake":
        pytest.skip("Snowflake target is covered by test_live_snowflake_ar_aging")
    else:
        pytest.fail(f"unknown WAREHOUSE_CONTRACT_TARGET: {target}")
    connection = ContractConnection(adapter)
    rows = LegacyReceivablesWarehouse(connect=lambda: connection).ar_aging()
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


def test_live_snowflake_ar_aging():
    required = ("ACCOUNT", "USER", "ROLE", "PRIVATE_KEY")
    if not all(os.getenv(f"SNOWFLAKE_{key}") for key in required):
        pytest.skip("Snowflake environment not configured")
    warehouse = SnowflakeReceivablesWarehouse(
        warehouse="SFX_D1110_PARITY_WH", database="SFX_D1110_AFTER",
    )
    try:
        rows = warehouse.ar_aging()
    finally:
        print(f"Snowflake query id: {warehouse.last_query_id}")
    recorded = json.loads((ROOT / "recorded/teradata/ar-aging.json").read_text())
    assert list(COLUMNS) == recorded["columns"]
    assert len(rows) == 100
    assert [(-Decimal(row["OPEN_BALANCE"]), row["ACCOUNT_NO"]) for row in rows] == sorted(
        (-Decimal(row["OPEN_BALANCE"]), row["ACCOUNT_NO"]) for row in rows
    )
    for row in rows:
        assert list(row) == recorded["columns"]
        assert date.fromisoformat(row["OLDEST_DUE_DATE"]).isoformat() == row["OLDEST_DUE_DATE"]
        for column in COLUMNS[4:]:
            assert isinstance(row[column], str)
            assert Decimal(row[column]).is_finite()
        assert sum(Decimal(row[column]) for column in (
            "CURRENT_AMT", "DAYS_1_30", "DAYS_31_60", "DAYS_61_90", "DAYS_OVER_90",
        )) == Decimal(row["OPEN_BALANCE"])
        assert 0 < Decimal(row["OPEN_RATIO"]) <= 1
