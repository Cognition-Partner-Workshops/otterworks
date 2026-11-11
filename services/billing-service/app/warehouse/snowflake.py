from __future__ import annotations

from collections.abc import Callable
from contextlib import closing
from datetime import date
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings

from app.warehouse import MAX_INVOICES, InvoiceExportRow

QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"billing-service"}'
SQL = """
WITH invoices AS (
    SELECT i.INVOICE_NUMBER, a.ACCOUNT_NAME, a.ACCOUNT_NUMBER, i.INVOICE_DT, i.CURRENCY_CD,
        i.TOTAL_AMOUNT, i.TAX_AMOUNT, i.TOTAL_AMOUNT - COALESCE(p.PAID, 0) AS OPEN_BALANCE
    FROM SFX_D1110_AFTER.COMPAT.INVOICE_HDR i
    JOIN SFX_D1110_AFTER.COMPAT.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = i.CUSTOMER_ID
    LEFT JOIN (
        SELECT INVOICE_ID, SUM(AMOUNT) AS PAID
        FROM SFX_D1110_AFTER.COMPAT.PAYMENT GROUP BY INVOICE_ID
    ) p ON p.INVOICE_ID = i.INVOICE_ID
    WHERE i.BILL_DT = DATEADD(day, -1, COALESCE(TO_DATE(%s), CURRENT_DATE))
        AND i.INVOICE_DT >= DATE '2020-01-01'
)
SELECT INVOICE_NUMBER AS INVOICE_NO, ACCOUNT_NAME AS CUSTOMER_NAME, ACCOUNT_NUMBER AS ACCOUNT_NO,
    TO_VARCHAR(INVOICE_DT, 'YYYY-MM-DD') AS INVOICE_DATE, CURRENCY_CD,
    TO_VARCHAR(TOTAL_AMOUNT, 'FM9999999999990.00') AS AMOUNT_DUE,
    TO_VARCHAR(TAX_AMOUNT, 'FM9999999999990.00') AS TAX_AMT,
    TO_VARCHAR(OPEN_BALANCE, 'FM9999999999990.00') AS OPEN_BALANCE
FROM invoices ORDER BY INVOICE_NUMBER LIMIT 100001
"""


class WarehouseSettings(BaseSettings):
    enabled: bool = Field(True, validation_alias="FINANCE_WAREHOUSE_ENABLED")
    account: str = ""
    user: str = ""
    role: str = ""
    warehouse: str = ""
    database: str = "SFX_D1110_AFTER"
    private_key: str = Field("", repr=False)
    query_tag: str = QUERY_TAG

    model_config = {"env_prefix": "SNOWFLAKE_", "extra": "ignore", "populate_by_name": True}

    def connection_kwargs(self) -> dict[str, Any]:
        missing = [
            key for key in ("account", "user", "role", "warehouse", "private_key")
            if not getattr(self, key)
        ]
        if missing:
            raise ValueError("missing Snowflake credentials: " + ", ".join(missing))
        from cryptography.hazmat.primitives import serialization

        key = serialization.load_pem_private_key(self.private_key.encode(), password=None)
        return {
            "account": self.account,
            "user": self.user,
            "role": self.role,
            "warehouse": self.warehouse,
            "database": self.database,
            "authenticator": "SNOWFLAKE_JWT",
            "private_key": key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            "session_parameters": {"QUERY_TAG": self.query_tag, "TIMEZONE": "UTC"},
        }


class SnowflakeInvoiceWarehouse:
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
        kwargs = self.settings.connection_kwargs()
        connect = self._connect
        if connect is None:
            import snowflake.connector

            connect = snowflake.connector.connect
        with closing(connect(**kwargs)) as connection, closing(connection.cursor()) as cursor:
            cursor.execute(SQL, [run_date.isoformat() if run_date else None])
            rows = cursor.fetchall()
        if len(rows) > MAX_INVOICES:
            raise RuntimeError("invoice export exceeds 100000 rows; narrow the export window")
        return [InvoiceExportRow.from_values(row) for row in rows]
