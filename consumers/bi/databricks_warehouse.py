"""Live Databricks read transport for bi-semantic."""
import os
import re
import sys
from pathlib import Path

for parent in Path(__file__).resolve().parents:
    kit = parent / "consumers" / "contract-kit"
    if kit.is_dir():
        sys.path.insert(0, str(kit))
        break
else:
    raise RuntimeError("consumer contract kit not found")

from databricks_client import execute as _execute

CONSUMER = "bi-semantic"
REQUIRED = ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID")


def configured():
    return all(os.getenv(name) for name in REQUIRED)


def execute(native_sql, parameters=(), step="contract"):
    return _execute(native_sql, parameters, consumer=CONSUMER, step=step)


def execute_with_id(native_sql, step="contract"):
    """Same tagged connection as the shared client, also returning the statement_id."""
    from databricks import sql

    run = os.environ.get("DATABRICKS_RUN_TOKEN", "dbx-d1111")
    for value in (run, step):
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
            cursor.execute(f"/* run={run} act=consumers step={step} consumer={CONSUMER} */\n"
                           + native_sql)
            return {"columns": [column[0].upper() for column in cursor.description],
                    "rows": [list(row) for row in cursor.fetchall()],
                    "statement_id": cursor.query_id}
