from __future__ import annotations

import json
import os
from contextlib import closing
from datetime import date
from decimal import Decimal

import pytest
from teradata_reference import SQL
from warehouse_clients import (
    ROOT,
    ContractConnection,
    EmulatorWarehouse,
)

from app.warehouse import MAX_INVOICES, InvoiceExportRow
from app.warehouse.snowflake import QUERY_TAG, SnowflakeInvoiceWarehouse, WarehouseSettings


def test_invoice_export_contract():
    target = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    if target in {"teradata-emulator", "replay", "snowflake-semantics"}:
        adapter = EmulatorWarehouse()
    elif target == "snowflake":
        return check_snowflake()
    else:
        pytest.fail(f"unknown WAREHOUSE_CONTRACT_TARGET: {target}")
    connection = ContractConnection(adapter)
    connection.execute(SQL, [date(2026, 11, 10).isoformat()])
    rows = [InvoiceExportRow.from_values(row) for row in connection.fetchall()]
    expected = json.loads((ROOT / "expected/invoice-export.json").read_text())
    assert connection.parameters == ["2026-11-10"]
    assert connection.result["query"] == expected["query"]
    assert len(rows) == expected["row_count"]
    assert [row.invoice_no for row in rows] == expected["keys"]
    attributes = {"AMOUNT_DUE": "amount_due", "TAX_AMT": "tax_amt", "OPEN_BALANCE": "open_balance"}
    for column, total in expected["sums"].items():
        assert sum((getattr(row, attributes[column]) for row in rows), Decimal(0)) == Decimal(total)


NATIVE_SQL = """
SELECT COUNT(*), SUM(i.TOTAL_AMOUNT), SUM(i.TAX_AMOUNT),
    SUM(i.TOTAL_AMOUNT - COALESCE(p.PAID, 0))
FROM SFX_D1110_AFTER.RAW_BILLING.INVOICE_HDR i
JOIN SFX_D1110_AFTER.RAW_BILLING.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = i.CUSTOMER_ID
LEFT JOIN (
    SELECT INVOICE_ID, SUM(AMOUNT) AS PAID
    FROM SFX_D1110_AFTER.RAW_BILLING.PAYMENT GROUP BY INVOICE_ID
) p ON p.INVOICE_ID = i.INVOICE_ID
WHERE i.BILL_DT = DATE '2026-11-09' AND i.INVOICE_DT >= DATE '2020-01-01'
"""


def check_snowflake():
    required = ("ACCOUNT", "USER", "ROLE", "PRIVATE_KEY")
    if not all(os.getenv(f"SNOWFLAKE_{key}") for key in required):
        pytest.skip("Snowflake environment not configured")
    connector = pytest.importorskip("snowflake.connector")
    settings = WarehouseSettings(
        warehouse=os.getenv("SNOWFLAKE_CONTRACT_WAREHOUSE", "SFX_D1110_PARITY_WH"),
        database="SFX_D1110_AFTER",
        query_tag=QUERY_TAG,
    )
    if settings.warehouse != "SFX_D1110_PARITY_WH":
        pytest.fail("contract warehouse must be SFX_D1110_PARITY_WH")
    results = {}

    class ObservedCursor:
        def __init__(self, cursor):
            self.cursor = cursor

        def execute(self, sql, parameters):
            self.cursor.execute(sql, parameters)
            print(f"Snowflake query ID: {self.cursor.sfqid}")
            results["columns"] = [column[0] for column in self.cursor.description]

        def fetchall(self):
            return self.cursor.fetchall()

        def close(self):
            self.cursor.close()

    class ObservedConnection:
        def __init__(self, **kwargs):
            self.connection = connector.connect(**kwargs)

        def cursor(self):
            return ObservedCursor(self.connection.cursor())

        def close(self):
            self.connection.close()

    rows = SnowflakeInvoiceWarehouse(settings, ObservedConnection).invoices_for_run(
        date(2026, 11, 10)
    )
    recorded = json.loads((ROOT / "recorded/teradata/invoice-export.json").read_text())
    expected = json.loads((ROOT / "expected/invoice-export.json").read_text())
    assert results["columns"] == recorded["columns"]
    keys = [row.invoice_no for row in rows]
    assert keys == sorted(keys)
    assert len(rows) <= MAX_INVOICES
    assert set(expected["keys"]) <= set(keys)
    assert [key for key in keys if key <= max(expected["keys"])] == expected["keys"]
    by_key = {row.invoice_no: row for row in rows}
    for values in recorded["rows"]:
        row = by_key[values[0]]
        assert row.invoice_date.isoformat() == values[3].strip()
        assert row.currency_cd == values[4].strip()

    with (
        closing(connector.connect(**settings.connection_kwargs())) as connection,
        closing(connection.cursor()) as cursor,
    ):
        cursor.execute(NATIVE_SQL)
        print(f"Snowflake query ID: {cursor.sfqid}")
        count, amount, tax, balance = cursor.fetchone()
    assert count == len(rows)
    for attribute, total in (
        ("amount_due", amount), ("tax_amt", tax), ("open_balance", balance)
    ):
        assert sum((getattr(row, attribute) for row in rows), Decimal(0)) == total
