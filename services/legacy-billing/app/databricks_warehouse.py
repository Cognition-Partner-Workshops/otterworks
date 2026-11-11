"""Live DB SQL connector transport for consumer adapters; SQL stays client-owned."""
import os
import re


def execute(statement, parameters=(), *, step="contract"):
    consumer = "legacy-billing"
    from databricks import sql

    run = os.environ.get("DATABRICKS_RUN_TOKEN", "dbx-d1111")
    if run != "dbx-d1111" or os.environ.get("DATABRICKS_CATALOG", "cpw") != "cpw":
        raise ValueError("unsupported Databricks run or catalog")
    for value in (run, consumer, step):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("invalid query tag")
    host = os.environ["DATABRICKS_HOST"].removeprefix("https://").rstrip("/")
    if "/" in host or not host.endswith(".databricks.com"):
        raise ValueError("invalid Databricks workspace host")
    warehouse = os.environ["DATABRICKS_WAREHOUSE_ID"]
    if not re.fullmatch(r"[a-f0-9]+", warehouse):
        raise ValueError("invalid warehouse id")
    with sql.connect(server_hostname=host,
                     http_path="/sql/1.0/warehouses/" + warehouse,
                     access_token=os.environ["DATABRICKS_TOKEN"],
                     catalog="cpw", schema="dbx_d1111_after") as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute(f"/* run={run} act=consumers step={step} consumer={consumer} */\n"
                               + statement, parameters)
            except Exception as error:
                error.statement_id = cursor.query_id
                raise
            return {"columns": [column[0].upper() for column in (cursor.description or [])],
                    "rows": [list(row) for row in cursor.fetchall()] if cursor.description else [],
                    "statement_id": cursor.query_id}
