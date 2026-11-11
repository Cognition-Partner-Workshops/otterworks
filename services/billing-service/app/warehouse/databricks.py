"""Live DB SQL connector transport for consumer adapters; SQL stays client-owned."""

import os
import re

from app.warehouse.teradata import MAX_INVOICES, InvoiceExportRow, WarehouseSettings

SQL = """
WITH invoices AS (
    SELECT i.INVOICE_NUMBER, a.ACCOUNT_NAME, a.ACCOUNT_NUMBER, i.INVOICE_DT, i.CURRENCY_CD,
        i.TOTAL_AMOUNT, i.TAX_AMOUNT, i.TOTAL_AMOUNT - COALESCE(p.PAID, 0) AS OPEN_BALANCE
    FROM cpw.dbx_d1111_after.billing__invoice_hdr i
    JOIN cpw.dbx_d1111_after.billing__customer_account a ON a.CUSTOMER_ID = i.CUSTOMER_ID
    LEFT JOIN (
        SELECT INVOICE_ID, SUM(AMOUNT) AS PAID
        FROM cpw.dbx_d1111_after.billing__payment GROUP BY INVOICE_ID
    ) p ON p.INVOICE_ID = i.INVOICE_ID
    WHERE i.BILL_DT = date_sub(COALESCE(CAST(? AS DATE), CURRENT_DATE()), 1)
        AND i.INVOICE_DT >= DATE '2020-01-01'
)
SELECT INVOICE_NUMBER AS INVOICE_NO, ACCOUNT_NAME AS CUSTOMER_NAME,
    ACCOUNT_NUMBER AS ACCOUNT_NO, INVOICE_DT AS INVOICE_DATE, CURRENCY_CD,
    CAST(TOTAL_AMOUNT AS DECIMAL(14,2)) AS AMOUNT_DUE,
    CAST(TAX_AMOUNT AS DECIMAL(14,2)) AS TAX_AMT,
    CAST(OPEN_BALANCE AS DECIMAL(14,2)) AS OPEN_BALANCE
FROM invoices ORDER BY INVOICE_NUMBER LIMIT 100001
"""

REQUIRED_ENV = ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID")


def execute(statement, parameters=(), *, step="contract"):
    consumer = "billing-service"
    from databricks import sql

    run = os.environ.get("DATABRICKS_RUN_TOKEN", "dbx-d1111")
    if run != "dbx-d1111" or os.environ.get("DATABRICKS_CATALOG", "cpw") != "cpw":
        raise ValueError("billing export is restricted to run dbx-d1111 in catalog cpw")
    for value in (run, consumer, step):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("invalid query tag")
    host = os.environ["DATABRICKS_HOST"].removeprefix("https://").rstrip("/")
    if "/" in host or not host.endswith(".databricks.com"):
        raise ValueError("invalid Databricks workspace host")
    warehouse = os.environ["DATABRICKS_WAREHOUSE_ID"]
    if not re.fullmatch(r"[a-f0-9]+", warehouse):
        raise ValueError("invalid warehouse id")
    with (
        sql.connect(
            server_hostname=host,
            http_path="/sql/1.0/warehouses/" + warehouse,
            access_token=os.environ["DATABRICKS_TOKEN"],
            catalog="cpw",
            schema="dbx_d1111_after",
        ) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            f"/* run={run} act=consumers step={step} consumer={consumer} */\n" + statement,
            parameters,
        )
        return {
            "columns": [column[0].upper() for column in cursor.description or ()],
            "rows": [list(row) for row in cursor.fetchall()] if cursor.description else [],
            "statement_id": cursor.query_id,
        }


class DatabricksInvoiceWarehouse:
    def __init__(self, settings=None, transport=None):
        self.settings = settings or WarehouseSettings()
        self._execute = transport or execute
        self.last_result = None

    def invoices_for_run(self, run_date):
        if not self.settings.enabled:
            raise RuntimeError("finance warehouse export is disabled")
        self.last_result = self._execute(
            SQL, [run_date.isoformat() if run_date else None], step="contract-fixed"
        )
        rows = self.last_result["rows"]
        if len(rows) > MAX_INVOICES:
            raise RuntimeError("invoice export exceeds 100000 rows; narrow the export window")
        return [InvoiceExportRow.from_values(row) for row in rows]
