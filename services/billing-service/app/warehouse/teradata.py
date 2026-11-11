from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib.resources import files
from typing import Any, Literal, Protocol
from urllib.parse import unquote, urlparse

from pydantic_settings import BaseSettings

SQL = """
WITH invoices AS (
    SEL i.INVOICE_NUMBER, a.ACCOUNT_NAME, a.ACCOUNT_NUMBER, i.INVOICE_DT, i.CURRENCY_CD,
        i.TOTAL_AMOUNT, i.TAX_AMOUNT, i.TOTAL_AMOUNT - ZEROIFNULL(p.PAID) AS OPEN_BALANCE
    FROM SFX_BILLING.INVOICE_HDR i
    JOIN SFX_BILLING.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = i.CUSTOMER_ID
    LEFT JOIN (
        SEL INVOICE_ID, SUM(AMOUNT) AS PAID FROM SFX_BILLING.PAYMENT GROUP BY INVOICE_ID
    ) p ON p.INVOICE_ID = i.INVOICE_ID
    WHERE i.BILL_DT = COALESCE(CAST(? AS DATE) - 1, CURRENT_DATE - 1)
        AND i.INVOICE_DT >= 1200101
)
SEL TOP 100001 INVOICE_NUMBER AS INVOICE_NO, ACCOUNT_NAME AS CUSTOMER_NAME,
    ACCOUNT_NUMBER AS ACCOUNT_NO,
    CAST(CAST(INVOICE_DT AS FORMAT 'YYYY-MM-DD') AS CHAR(10)) AS INVOICE_DATE, CURRENCY_CD,
    CAST(CAST(TOTAL_AMOUNT AS FORMAT '9999999999999.99') AS CHAR(20)) AS AMOUNT_DUE,
    CAST(CAST(TAX_AMOUNT AS FORMAT '9999999999999.99') AS CHAR(20)) AS TAX_AMT,
    CAST(CAST(OPEN_BALANCE AS FORMAT '9999999999999.99') AS CHAR(20)) AS OPEN_BALANCE
FROM invoices ORDER BY INVOICE_NUMBER
"""
MAX_INVOICES = 100000


class WarehouseSettings(BaseSettings):
    enabled: bool = True
    target: Literal["databricks", "teradata"] = "databricks"
    dsn: str = tomllib.loads(files("app.warehouse").joinpath("config.toml").read_text())["dsn"]

    model_config = {"env_prefix": "FINANCE_WAREHOUSE_", "extra": "ignore"}


@dataclass(frozen=True)
class InvoiceExportRow:
    invoice_no: str
    customer_name: str
    account_no: str
    invoice_date: date
    currency_cd: str
    amount_due: Decimal
    tax_amt: Decimal
    open_balance: Decimal

    @classmethod
    def from_values(cls, values: list[Any] | tuple[Any, ...]) -> InvoiceExportRow:
        invoice_no, customer, account, issued, currency, amount, tax, balance = values
        return cls(
            str(invoice_no),
            str(customer),
            str(account).strip(),
            issued if isinstance(issued, date) else date.fromisoformat(str(issued).strip()),
            str(currency).strip(),
            Decimal(str(amount).strip()),
            Decimal(str(tax).strip()),
            Decimal(str(balance).strip()),
        )


class InvoiceWarehouse(Protocol):
    def invoices_for_run(self, run_date: date | None) -> list[InvoiceExportRow]: ...


class TeradataInvoiceWarehouse:
    def __init__(
        self,
        settings: WarehouseSettings | None = None,
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self.settings = settings or WarehouseSettings()
        self._connect = connect

    def invoices_for_run(self, run_date: date | None) -> list[InvoiceExportRow]:
        if not self.settings.enabled:
            raise RuntimeError("finance warehouse export is disabled")
        connect = self._connect
        if connect is None:
            import teradatasql

            connect = teradatasql.connect
        dsn = urlparse(self.settings.dsn)
        if dsn.scheme != "teradata" or not dsn.hostname or not dsn.path.strip("/"):
            raise ValueError("invalid finance warehouse DSN")
        with (
            connect(
                host=dsn.hostname,
                user=unquote(dsn.username or ""),
                password=unquote(dsn.password or ""),
                database=dsn.path.strip("/"),
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(SQL, [run_date.isoformat() if run_date else None])
            rows = cursor.fetchall()
        if len(rows) > MAX_INVOICES:
            raise RuntimeError("invoice export exceeds 100000 rows; narrow the export window")
        return [InvoiceExportRow.from_values(row) for row in rows]
