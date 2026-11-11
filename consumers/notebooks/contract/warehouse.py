"""Contract warehouse target ports."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import os
import sys
from pathlib import Path
from typing import Protocol
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / 'consumers' / 'contract-kit'))
from contract_client import execute as execute_contract

sys.path.insert(0, str(ROOT.parent))
from finance_nb.databricks_queries import native_sql, pin_teradata

AS_OF = os.getenv("CONTRACT_AS_OF") or None
BASELINE = ROOT / "recorded" / "live-baseline"


class Warehouse(Protocol):
    def query(self, sql: str) -> list[dict]: ...


def rows_of(data):
    return [dict(zip(data["columns"], row, strict=True)) for row in data["rows"]]


class EmulatorWarehouse:
    def __init__(self, queries):
        self.names = {sql: name for name, sql in queries.items()}

    def query(self, sql):
        return rows_of(execute_contract(pin_teradata(sql, AS_OF), ROOT, self.names[sql]))


class DatabricksWarehouse:
    """Live target: native rewrite of each notebook query on cpw.dbx_d1111_after."""
    CREDENTIALS = ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID")
    DEFAULT_AS_OF = "2026-11-09"

    def __init__(self, queries):
        self.names = {sql: name for name, sql in queries.items()}
        self.as_of = AS_OF or self.DEFAULT_AS_OF
        self.run_id = os.getenv("CONTRACT_RUN_ID") or uuid4().hex[:12]
        self.configured = all(os.getenv(key) for key in self.CREDENTIALS)

    def query(self, sql):
        if not self.configured:
            raise ValueError("Databricks environment not configured")
        from finance_nb.databricks_warehouse import execute
        name = self.names[sql]
        data = execute(native_sql(name, self.as_of), step=os.getenv("CONTRACT_STEP", "contract"),
                       label=f"{name}.{self.run_id}")
        return rows_of(data)


class SnowflakeWarehouse:
    DATABASE = "SFX_D1110_AFTER"
    SCHEMA = "COMPAT"
    QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"finance-notebook"}'

    def __init__(self):
        self.credentials = {
            key: os.getenv(f"SNOWFLAKE_{key}")
            for key in ("ACCOUNT", "USER", "ROLE", "WAREHOUSE", "PRIVATE_KEY")
        }

    def query(self, sql):
        if not all(self.credentials.values()):
            raise ValueError("Snowflake environment not configured")
        raise NotImplementedError(
            f"Snowflake adapter not installed; execute supplied SQL in "
            f"{self.DATABASE}.{self.SCHEMA} with QUERY_TAG={self.QUERY_TAG}"
        )


def canonical(value):
    """Order-preserving comparison form shared by both read paths."""
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (int, Decimal)):
        return Decimal(value).normalize()
    try:
        return Decimal(str(value)).normalize()
    except InvalidOperation:
        return str(value).rstrip()


def canonical_rows(rows):
    return [{column: canonical(value) for column, value in row.items()} for row in rows]


def load_baseline(name):
    return rows_of(json.loads((BASELINE / f"{name}.json").read_text()))


def target(queries):
    name = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    if name in {"teradata-emulator", "replay", "snowflake-semantics"}:
        return EmulatorWarehouse(queries)
    if name == "databricks":
        return DatabricksWarehouse(queries)
    if name == "snowflake":
        return SnowflakeWarehouse()
    raise ValueError(f"unknown warehouse contract target: {name}")
