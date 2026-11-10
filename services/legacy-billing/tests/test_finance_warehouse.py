from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from finance_warehouse import COLUMNS, SQL, TeradataReceivablesWarehouse


VALUES = (
    "A000318274", "Bramblewood Outfitters", "USD", date(2025, 10, 15),
    Decimal("6000.00"), Decimal("1000.00"), Decimal("1200.00"),
    Decimal("800.00"), Decimal("500.00"), Decimal("2500.00"), Decimal("0.75"),
)


def test_dal_executes_query_maps_decimals_and_closes():
    connect = MagicMock()
    cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [VALUES]
    result = TeradataReceivablesWarehouse(connect=connect).ar_aging()
    cursor.execute.assert_called_once_with(SQL)
    connect.assert_called_once_with(
        host="tdprod-fin.otterworks.internal", user="svc_legacy_billing",
        password="not-a-real-password", database="FIN_DW",  # gitleaks:allow
    )
    assert result == [dict(zip(COLUMNS, (
        "A000318274", "Bramblewood Outfitters", "USD", "2025-10-15",
        "6000.00", "1000.00", "1200.00", "800.00", "500.00", "2500.00", "0.75",
    ), strict=True))]
    assert connect.return_value.__exit__.called


def test_dal_empty_results():
    connect = MagicMock()
    cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    assert TeradataReceivablesWarehouse(connect=connect).ar_aging() == []


def test_dal_query_error_closes_connection():
    connect = MagicMock()
    cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        TeradataReceivablesWarehouse(connect=connect).ar_aging()
    assert connect.return_value.__exit__.called


def test_null_ratio_and_formatted_values():
    values = list(VALUES)
    values[0] += " "
    values[2] += " "
    values[3] = "2025-10-15"
    values[4] = "   6000.00"
    values[-1] = None
    result = TeradataReceivablesWarehouse._map_row(values)
    assert result["ACCOUNT_NO"] == "A000318274"
    assert result["CURRENCY_CD"] == "USD"
    assert result["OPEN_BALANCE"] == "6000.00"
    assert result["OPEN_RATIO"] is None
