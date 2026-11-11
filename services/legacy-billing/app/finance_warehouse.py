from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import closing
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

SQL = """WITH receivables AS (
    SELECT i.CUSTOMER_ID, DATEADD(day, 30, i.INVOICE_DT) AS DUE_DT, i.CURRENCY_CD,
        i.TOTAL_AMOUNT AS AMOUNT_DUE, i.TOTAL_AMOUNT - COALESCE(p.PAID, 0) AS OPEN_BALANCE
    FROM SFX_D1110_AFTER.COMPAT.INVOICE_HDR i
    JOIN SFX_D1110_AFTER.COMPAT.CUSTOMER_ACCOUNT ia ON ia.CUSTOMER_ID = i.CUSTOMER_ID
    LEFT JOIN (
        SELECT INVOICE_ID, SUM(AMOUNT) AS PAID FROM SFX_D1110_AFTER.COMPAT.PAYMENT GROUP BY INVOICE_ID
    ) p ON p.INVOICE_ID = i.INVOICE_ID
    WHERE i.INVOICE_DT >= DATE '2020-01-01'
        AND i.TOTAL_AMOUNT - COALESCE(p.PAID, 0) > 0
)
SELECT a.ACCOUNT_NUMBER AS ACCOUNT_NO, a.ACCOUNT_NAME AS CUSTOMER_NAME, i.CURRENCY_CD,
    MIN(i.DUE_DT) AS OLDEST_DUE_DATE, SUM(i.OPEN_BALANCE) AS OPEN_BALANCE,
    SUM(CASE WHEN DATEDIFF(day, i.DUE_DT, CURRENT_DATE) <= 0 THEN i.OPEN_BALANCE ELSE 0 END) AS CURRENT_AMT,
    SUM(CASE WHEN DATEDIFF(day, i.DUE_DT, CURRENT_DATE) BETWEEN 1 AND 30 THEN i.OPEN_BALANCE ELSE 0 END) AS DAYS_1_30,
    SUM(CASE WHEN DATEDIFF(day, i.DUE_DT, CURRENT_DATE) BETWEEN 31 AND 60 THEN i.OPEN_BALANCE ELSE 0 END) AS DAYS_31_60,
    SUM(CASE WHEN DATEDIFF(day, i.DUE_DT, CURRENT_DATE) BETWEEN 61 AND 90 THEN i.OPEN_BALANCE ELSE 0 END) AS DAYS_61_90,
    SUM(CASE WHEN DATEDIFF(day, i.DUE_DT, CURRENT_DATE) > 90 THEN i.OPEN_BALANCE ELSE 0 END) AS DAYS_OVER_90,
    SUM(i.OPEN_BALANCE) / NULLIF(SUM(i.AMOUNT_DUE), 0) AS OPEN_RATIO
FROM receivables i
JOIN SFX_D1110_AFTER.COMPAT.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = i.CUSTOMER_ID
GROUP BY a.ACCOUNT_NUMBER, a.ACCOUNT_NAME, i.CURRENCY_CD
ORDER BY OPEN_BALANCE DESC, a.ACCOUNT_NUMBER, i.CURRENCY_CD
LIMIT 100
"""
COLUMNS = (
    "ACCOUNT_NO", "CUSTOMER_NAME", "CURRENCY_CD", "OLDEST_DUE_DATE", "OPEN_BALANCE",
    "CURRENT_AMT", "DAYS_1_30", "DAYS_31_60", "DAYS_61_90", "DAYS_OVER_90", "OPEN_RATIO",
)


class ReceivablesWarehouse(Protocol):
    def ar_aging(self) -> list[dict[str, Any]]: ...


QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"legacy-billing"}'


class SnowflakeReceivablesWarehouse:
    def __init__(
        self, warehouse: str | None = None, connect: Callable[..., Any] | None = None,
        database: str | None = None,
    ) -> None:
        self.warehouse = warehouse
        self.database = database
        self._connect = connect
        self.last_query_id: str | None = None

    def ar_aging(self) -> list[dict[str, Any]]:
        credentials = {
            key.lower(): os.getenv(f"SNOWFLAKE_{key}")
            for key in ("ACCOUNT", "USER", "ROLE", "PRIVATE_KEY")
        }
        missing = [f"SNOWFLAKE_{key.upper()}" for key, value in credentials.items() if not value]
        if missing:
            raise ValueError("Missing Snowflake credentials: " + ", ".join(missing))
        from cryptography.hazmat.primitives import serialization

        key = serialization.load_pem_private_key(
            credentials.pop("private_key").encode(), password=None,
        )
        private_key = key.private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        connect = self._connect
        if connect is None:
            import snowflake.connector

            connect = snowflake.connector.connect
        self.last_query_id = None
        with closing(connect(
            **credentials, private_key=private_key, authenticator="SNOWFLAKE_JWT",
            database=self.database or os.getenv("SNOWFLAKE_DATABASE", "SFX_D1110_AFTER"),
            warehouse=self.warehouse or os.getenv("SNOWFLAKE_WAREHOUSE"),
            session_parameters={"QUERY_TAG": QUERY_TAG, "TIMEZONE": "UTC"},
        )) as connection, closing(connection.cursor()) as cursor:
            try:
                cursor.execute(SQL)
            finally:
                self.last_query_id = getattr(cursor, "sfqid", None)
            values = cursor.fetchall()
        return [self._map_row(row) for row in values]

    @staticmethod
    def _map_row(row: list[Any] | tuple[Any, ...]) -> dict[str, Any]:
        mapped = dict(zip(COLUMNS, row, strict=True))
        for column in COLUMNS[4:]:
            if mapped[column] is not None:
                mapped[column] = str(Decimal(str(mapped[column]).strip()))
        due = mapped["OLDEST_DUE_DATE"]
        mapped["OLDEST_DUE_DATE"] = (
            due.isoformat() if isinstance(due, date) else str(due).strip()
        )
        mapped["ACCOUNT_NO"] = str(mapped["ACCOUNT_NO"]).strip()
        mapped["CURRENCY_CD"] = str(mapped["CURRENCY_CD"]).strip()
        return mapped
