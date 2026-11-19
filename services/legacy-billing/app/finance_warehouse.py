from __future__ import annotations

import os
from collections.abc import Callable
from configparser import ConfigParser
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

SQL = """
WITH receivables AS (
    SEL i.CUSTOMER_ID, i.INVOICE_DT + 30 AS DUE_DT, i.CURRENCY_CD, i.TOTAL_AMOUNT AS AMOUNT_DUE,
        i.TOTAL_AMOUNT - ZEROIFNULL(p.PAID) AS OPEN_BALANCE
    FROM SFX_BILLING.V_ACCOUNT_INVOICES i
    LEFT JOIN (
        SEL INVOICE_ID, SUM(AMOUNT) AS PAID FROM SFX_BILLING.PAYMENT GROUP BY INVOICE_ID
    ) p ON p.INVOICE_ID = i.INVOICE_ID
    WHERE i.INVOICE_DT >= 1200101
        AND i.TOTAL_AMOUNT - ZEROIFNULL(p.PAID) > 0
)
SEL TOP 100 a.ACCOUNT_NUMBER AS ACCOUNT_NO, a.ACCOUNT_NAME AS CUSTOMER_NAME, i.CURRENCY_CD,
    CAST(MIN(i.DUE_DT) AS DATE FORMAT 'YYYY-MM-DD') AS OLDEST_DUE_DATE,
    SUM(i.OPEN_BALANCE) AS OPEN_BALANCE,
    ZEROIFNULL(SUM(CASE WHEN CURRENT_DATE - i.DUE_DT <= 0
        THEN i.OPEN_BALANCE ELSE 0 END)) AS CURRENT_AMT,
    ZEROIFNULL(SUM(CASE WHEN CURRENT_DATE - i.DUE_DT BETWEEN 1 AND 30
        THEN i.OPEN_BALANCE ELSE 0 END)) AS DAYS_1_30,
    ZEROIFNULL(SUM(CASE WHEN CURRENT_DATE - i.DUE_DT BETWEEN 31 AND 60
        THEN i.OPEN_BALANCE ELSE 0 END)) AS DAYS_31_60,
    ZEROIFNULL(SUM(CASE WHEN CURRENT_DATE - i.DUE_DT BETWEEN 61 AND 90
        THEN i.OPEN_BALANCE ELSE 0 END)) AS DAYS_61_90,
    ZEROIFNULL(SUM(CASE WHEN CURRENT_DATE - i.DUE_DT > 90
        THEN i.OPEN_BALANCE ELSE 0 END)) AS DAYS_OVER_90,
    SUM(i.OPEN_BALANCE) / NULLIFZERO(SUM(i.AMOUNT_DUE)) AS OPEN_RATIO
FROM receivables i
JOIN SFX_BILLING.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = i.CUSTOMER_ID
GROUP BY a.ACCOUNT_NUMBER, a.ACCOUNT_NAME, i.CURRENCY_CD
ORDER BY OPEN_BALANCE DESC, a.ACCOUNT_NUMBER, i.CURRENCY_CD
"""
COLUMNS = (
    "ACCOUNT_NO", "CUSTOMER_NAME", "CURRENCY_CD", "OLDEST_DUE_DATE", "OPEN_BALANCE",
    "CURRENT_AMT", "DAYS_1_30", "DAYS_31_60", "DAYS_61_90", "DAYS_OVER_90", "OPEN_RATIO",
)


class ReceivablesWarehouse(Protocol):
    def ar_aging(self) -> list[dict[str, Any]]: ...


def default_dsn() -> str:
    config = ConfigParser(interpolation=None)
    config.read(Path(__file__).with_suffix(".ini"))
    return config["warehouse"]["dsn"]


class TeradataReceivablesWarehouse:
    def __init__(
        self, dsn: str | None = None, connect: Callable[..., Any] | None = None,
    ) -> None:
        self.dsn = dsn or os.getenv("FINANCE_WAREHOUSE_DSN") or default_dsn()
        self._connect = connect

    def ar_aging(self) -> list[dict[str, Any]]:
        connect = self._connect
        if connect is None:
            import teradatasql

            connect = teradatasql.connect
        dsn = urlparse(self.dsn)
        if dsn.scheme != "teradata" or not dsn.hostname or not dsn.path.strip("/"):
            raise ValueError("invalid finance warehouse DSN")
        with connect(
            host=dsn.hostname, user=unquote(dsn.username or ""),
            password=unquote(dsn.password or ""), database=dsn.path.strip("/"),
        ) as connection, connection.cursor() as cursor:
            cursor.execute(SQL)
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
