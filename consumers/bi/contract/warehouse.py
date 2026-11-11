"""Contract warehouse target ports."""
import os
import sys
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / 'consumers' / 'contract-kit'))
from contract_client import execute as execute_contract


class Warehouse(Protocol):
    def query(self, sql: str) -> list[dict]: ...


class EmulatorWarehouse:
    def __init__(self, queries):
        self.names = {sql: name for name, sql in queries.items()}

    def query(self, sql):
        data = execute_contract(sql, ROOT, self.names[sql])
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


def target(queries):
    name = os.getenv("WAREHOUSE_CONTRACT_TARGET", "teradata-emulator")
    if name in {"teradata-emulator", "replay", "snowflake-semantics"}:
        return EmulatorWarehouse(queries)
    if name == "snowflake":
        return SnowflakeWarehouse()
    raise ValueError(f"unknown warehouse contract target: {name}")
