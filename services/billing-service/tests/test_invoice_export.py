from __future__ import annotations

import csv
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.export_invoices import export_invoices, main
from app.warehouse import InvoiceExportRow
from app.warehouse.snowflake import (
    QUERY_TAG,
    SQL,
    SnowflakeInvoiceWarehouse,
    WarehouseSettings,
)


def settings():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return WarehouseSettings(
        account="test", user="test", role="test", warehouse="test", private_key=pem
    )


ROW = InvoiceExportRow(
    "INV-2026-004812",
    "Sample Account, Ltd",
    "A000318274",
    date(2026, 1, 5),
    "USD",
    Decimal("4800.00"),
    Decimal("800.00"),
    Decimal("3600.00"),
)


class FakeWarehouse:
    def __init__(self, rows=None, error=None):
        self.rows = [ROW] if rows is None else rows
        self.error = error
        self.run_date = None

    def invoices_for_run(self, run_date):
        self.run_date = run_date
        if self.error:
            raise self.error
        return self.rows


def test_csv_export_quotes_names_and_preserves_decimals(tmp_path):
    warehouse = FakeWarehouse()
    out = tmp_path / "invoices.csv"
    assert export_invoices(warehouse, date(2026, 1, 6), out) == 1
    assert warehouse.run_date == date(2026, 1, 6)
    with out.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows == [
        {
            "invoice_no": ROW.invoice_no,
            "customer_name": ROW.customer_name,
            "account_no": ROW.account_no,
            "invoice_date": "2026-01-05",
            "currency_cd": "USD",
            "amount_due": "4800.00",
            "tax_amt": "800.00",
            "open_balance": "3600.00",
        }
    ]


def test_empty_export_writes_header(tmp_path):
    out = tmp_path / "empty.csv"
    assert export_invoices(FakeWarehouse([]), None, out) == 0
    assert out.read_text().splitlines() == [
        "invoice_no,customer_name,account_no,invoice_date,currency_cd,amount_due,tax_amt,open_balance"
    ]


def test_disabled_export_never_reads_or_writes(tmp_path):
    warehouse = FakeWarehouse(error=AssertionError("must not query"))
    with pytest.raises(RuntimeError, match="disabled"):
        export_invoices(warehouse, None, tmp_path / "invoices.csv", enabled=False)
    assert not list(tmp_path.iterdir())


def test_query_error_preserves_existing_output(tmp_path):
    out = tmp_path / "invoices.csv"
    out.write_text("previous export")
    with pytest.raises(RuntimeError, match="unavailable"):
        export_invoices(FakeWarehouse(error=RuntimeError("unavailable")), None, out)
    assert out.read_text() == "previous export"


def test_output_error_cleans_temporary_file(tmp_path, monkeypatch):
    import app.export_invoices as module

    class BrokenWriter:
        def writeheader(self):
            raise OSError("disk full")

    monkeypatch.setattr(module.csv, "DictWriter", lambda *args, **kwargs: BrokenWriter())
    with pytest.raises(OSError, match="disk full"):
        export_invoices(FakeWarehouse(), None, tmp_path / "invoices.csv")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("run_date,parameter", [(date(2026, 1, 6), "2026-01-06"), (None, None)])
def test_dal_executes_sql_and_maps_values(run_date, parameter):
    connect = MagicMock()
    cursor = connect.return_value.cursor.return_value
    cursor.fetchall.return_value = [
        (
            "INV-2026-004812",
            ROW.customer_name,
            "A000318274 ",
            "2026-01-05",
            "USD",
            "         4800.00",
            "          800.00",
            "         3600.00",
        )
    ]
    result = SnowflakeInvoiceWarehouse(settings(), connect).invoices_for_run(run_date)
    assert result == [ROW]
    cursor.execute.assert_called_once_with(SQL, [parameter])
    kwargs = connect.call_args.kwargs
    assert kwargs["authenticator"] == "SNOWFLAKE_JWT"
    assert kwargs["session_parameters"] == {"QUERY_TAG": QUERY_TAG, "TIMEZONE": "UTC"}
    assert isinstance(kwargs["private_key"], bytes)
    assert "teradatasql" not in sys.modules
    assert connect.return_value.close.called
    assert cursor.close.called


def test_dal_empty_and_row_limit():
    connect = MagicMock()
    cursor = connect.return_value.cursor.return_value
    cursor.fetchall.return_value = []
    warehouse = SnowflakeInvoiceWarehouse(settings(), connect=connect)
    assert warehouse.invoices_for_run(None) == []
    cursor.fetchall.return_value = [None] * 100001
    with pytest.raises(RuntimeError, match="exceeds"):
        warehouse.invoices_for_run(None)


def test_dal_initialization_does_not_import_driver(monkeypatch):
    monkeypatch.setitem(sys.modules, "teradatasql", None)
    warehouse = SnowflakeInvoiceWarehouse(WarehouseSettings(enabled=False))
    with pytest.raises(RuntimeError, match="disabled"):
        warehouse.invoices_for_run(None)


def test_dal_closes_on_query_failure():
    connect = MagicMock()
    cursor = connect.return_value.cursor.return_value
    cursor.execute.side_effect = RuntimeError("private details")
    with pytest.raises(RuntimeError, match="private details"):
        SnowflakeInvoiceWarehouse(settings(), connect=connect).invoices_for_run(None)
    assert connect.return_value.close.called
    assert cursor.close.called


def test_cli_calls_export_and_rejects_bad_date(tmp_path, monkeypatch, capsys):
    import app.export_invoices as module

    warehouse = FakeWarehouse()
    monkeypatch.setattr(module, "SnowflakeInvoiceWarehouse", lambda settings: warehouse)
    out = tmp_path / "invoices.csv"
    assert main(["--date", "2026-01-06", "--out", str(out)]) == 0
    assert warehouse.run_date == date(2026, 1, 6)
    assert "Exported 1 invoices" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        main(["--date", "2026-02-30", "--out", str(out)])
    assert exc.value.code == 2


def test_cli_disabled_and_errors_are_sanitized(tmp_path, monkeypatch, capsys):
    import app.export_invoices as module

    monkeypatch.setenv("FINANCE_WAREHOUSE_ENABLED", "false")
    assert main(["--out", str(tmp_path / "invoices.csv")]) == 1
    assert not list(tmp_path.iterdir())
    monkeypatch.setenv("FINANCE_WAREHOUSE_ENABLED", "true")
    monkeypatch.setattr(
        module,
        "SnowflakeInvoiceWarehouse",
        lambda settings: FakeWarehouse(error=RuntimeError("private connection details")),
    )
    assert main(["--out", str(tmp_path / "invoices.csv")]) == 1
    assert "private" not in capsys.readouterr().err


def test_missing_credentials_fail_before_connect():
    connect = MagicMock()
    with pytest.raises(ValueError, match="missing Snowflake credentials"):
        SnowflakeInvoiceWarehouse(
            WarehouseSettings(account="", user="", private_key=""), connect
        ).invoices_for_run(None)
    connect.assert_not_called()


def test_app_has_no_legacy_driver_or_login():
    root = Path(__file__).resolve().parents[1] / "app"
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".toml"}:
            source = path.read_text()
            assert "teradatasql" not in source
            assert "svc_billing_export" not in source
