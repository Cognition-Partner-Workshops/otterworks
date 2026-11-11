from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import pytest

from finance_warehouse import COLUMNS, SQL, SnowflakeReceivablesWarehouse


VALUES = (
    "A000318274", "Bramblewood Outfitters", "USD", date(2025, 10, 15),
    Decimal("6000.00"), Decimal("1000.00"), Decimal("1200.00"),
    Decimal("800.00"), Decimal("500.00"), Decimal("2500.00"), Decimal("0.75"),
)


def test_dal_executes_query_maps_decimals_and_closes():
    connect = MagicMock()
    cursor = connect.return_value.cursor.return_value
    cursor.fetchall.return_value = [VALUES]
    cursor.sfqid = "query-123"
    warehouse = SnowflakeReceivablesWarehouse(connect=connect)
    result = warehouse.ar_aging()
    assert warehouse.last_query_id == "query-123"
    cursor.execute.assert_called_once_with(SQL)
    kwargs = connect.call_args.kwargs
    key = serialization.load_der_private_key(kwargs.pop("private_key"), password=None)
    assert isinstance(key, rsa.RSAPrivateKey)
    assert kwargs == {
        "account": "test-account", "user": "test-user", "role": "test-role",
        "database": "SFX_D1110_AFTER", "warehouse": "test-warehouse",
        "authenticator": "SNOWFLAKE_JWT",
        "session_parameters": {
            "QUERY_TAG": '{"run":"sfx-d1110","act":"consumers","consumer":"legacy-billing"}',
            "TIMEZONE": "UTC",
        },
    }
    connect.assert_called_once()
    assert result == [dict(zip(COLUMNS, (
        "A000318274", "Bramblewood Outfitters", "USD", "2025-10-15",
        "6000.00", "1000.00", "1200.00", "800.00", "500.00", "2500.00", "0.75",
    ), strict=True))]
    connect.return_value.close.assert_called_once()
    cursor.close.assert_called_once()


def test_dal_empty_results():
    connect = MagicMock()
    cursor = connect.return_value.cursor.return_value
    cursor.fetchall.return_value = []
    assert SnowflakeReceivablesWarehouse(connect=connect).ar_aging() == []


def test_dal_query_error_closes_connection():
    connect = MagicMock()
    cursor = connect.return_value.cursor.return_value
    cursor.execute.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        SnowflakeReceivablesWarehouse(connect=connect).ar_aging()
    connect.return_value.close.assert_called_once()
    cursor.close.assert_called_once()


def test_null_ratio_and_formatted_values():
    values = list(VALUES)
    values[0] += " "
    values[2] += " "
    values[3] = "2025-10-15"
    values[4] = "   6000.00"
    values[-1] = None
    result = SnowflakeReceivablesWarehouse._map_row(values)
    assert result["ACCOUNT_NO"] == "A000318274"
    assert result["CURRENCY_CD"] == "USD"
    assert result["OPEN_BALANCE"] == "6000.00"
    assert result["OPEN_RATIO"] is None


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    for name, value in {
        "ACCOUNT": "test-account", "USER": "test-user", "ROLE": "test-role",
        "PRIVATE_KEY": pem, "WAREHOUSE": "test-warehouse",
    }.items():
        monkeypatch.setenv(f"SNOWFLAKE_{name}", value)
    monkeypatch.delenv("SNOWFLAKE_DATABASE", raising=False)


@pytest.mark.parametrize("name", ["ACCOUNT", "USER", "ROLE", "PRIVATE_KEY"])
def test_missing_credentials(monkeypatch, name):
    monkeypatch.delenv(f"SNOWFLAKE_{name}")
    connect = MagicMock()
    with pytest.raises(ValueError, match=f"Missing Snowflake credentials: SNOWFLAKE_{name}"):
        SnowflakeReceivablesWarehouse(connect=connect).ar_aging()
    connect.assert_not_called()


def test_constructor_overrides(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "environment-db")
    connect = MagicMock()
    connect.return_value.cursor.return_value.fetchall.return_value = []
    SnowflakeReceivablesWarehouse(
        warehouse="SFX_D1110_PARITY_WH", database="SFX_D1110_AFTER", connect=connect,
    ).ar_aging()
    assert connect.call_args.kwargs["warehouse"] == "SFX_D1110_PARITY_WH"
    assert connect.call_args.kwargs["database"] == "SFX_D1110_AFTER"


def test_app_has_no_legacy_driver_or_service_account():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    for path in app_dir.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            content = path.read_text()
            assert "svc_legacy_billing" not in content, path
            assert "teradatasql" not in content, path
