from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib.resources import files
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

from pydantic_settings import BaseSettings

SQL = """
SEL TOP 100001 i.INVOICE_NO, c.CUSTOMER_NAME, a.ACCOUNT_NO,
    (i.INVOICE_DT (FORMAT 'YYYY-MM-DD') (CHAR(10))) AS INVOICE_DATE,
    i.CURRENCY_CD,
    (i.AMOUNT_DUE (FORMAT 'Z(12)9.99') (CHAR(16))) AS AMOUNT_DUE,
    (i.TAX_AMT (FORMAT 'Z(12)9.99') (CHAR(16))) AS TAX_AMT,
    ((i.AMOUNT_DUE - ZEROIFNULL(p.PAID)) (FORMAT 'Z(12)9.99') (CHAR(16))) AS OPEN_BALANCE
FROM FIN_DW.INVOICE i
JOIN FIN_DW.ACCOUNT a ON a.ACCOUNT_ID = i.ACCOUNT_ID
JOIN FIN_DW.CUSTOMER c ON c.CUSTOMER_ID = a.CUSTOMER_ID
LEFT JOIN (
    SEL INVOICE_ID, SUM(AMOUNT) AS PAID FROM FIN_DW.PAYMENT GROUP BY INVOICE_ID
) p ON p.INVOICE_ID = i.INVOICE_ID
WHERE i.INVOICE_DT = COALESCE(CAST(? AS DATE) - 1, CURRENT_DATE - 1)
    AND i.INVOICE_DT >= 1200101
ORDER BY i.INVOICE_NO, i.INVOICE_ID
"""
MAX_INVOICES = 100000


class WarehouseSettings(BaseSettings):
    enabled: bool = True
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
