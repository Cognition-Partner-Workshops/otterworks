"""Contract warehouse target ports."""
import os
import re
import sys
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / 'consumers' / 'contract-kit'))
from contract_client import execute as execute_contract

AS_OF_DATE = os.getenv("CONTRACT_AS_OF_DATE", "2026-11-09")


def pin_as_of(sql, as_of=AS_OF_DATE):
    """Replace CURRENT_DATE / current_date() with the contract as-of date on either dialect."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
        raise ValueError("CONTRACT_AS_OF_DATE must be YYYY-MM-DD")
    return re.sub(r"\bCURRENT_DATE\b(\s*\(\s*\))?", f"DATE '{as_of}'", sql, flags=re.I)


class Warehouse(Protocol):
    def query(self, sql: str) -> list[dict]: ...


class EmulatorWarehouse:
    def __init__(self, queries):
        self.names = {sql: name for name, sql in queries.items()}

    def query(self, sql):
        data = execute_contract(sql, ROOT, self.names[sql])
        return [dict(zip(data["columns"], row, strict=True)) for row in data["rows"]]


class DatabricksWarehouse:
    """Runs the Databricks-dialect LookML SQL against cpw.dbx_d1111_after, as of AS_OF_DATE."""
    CATALOG = "cpw"
    SCHEMA = "dbx_d1111_after"

    def __init__(self, step="contract"):
        sys.path.insert(0, str(ROOT.parent))
        import databricks_warehouse
        self.transport = databricks_warehouse
        self.step = step
        self.statement_ids = {}

    def configured(self):
        return self.transport.configured()

    def query(self, sql, name=None):
        data = self.transport.execute_with_id(pin_as_of(sql), step=self.step)
        if name:
            self.statement_ids[name] = data["statement_id"]
        return [dict(zip(data["columns"], row, strict=True)) for row in data["rows"]]


class SnowflakeWarehouse:
    DATABASE = "SFX_D1110_AFTER"
    SCHEMA = "COMPAT"
    QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"bi-semantic"}'

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


def target_name():
    return os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")


def target(queries):
    name = target_name()
    if name in {"teradata-emulator", "replay", "snowflake-semantics"}:
        return EmulatorWarehouse(queries)
    if name == "snowflake":
        return SnowflakeWarehouse()
    if name == "databricks":
        return DatabricksWarehouse()
    raise ValueError(f"unknown warehouse contract target: {name}")
