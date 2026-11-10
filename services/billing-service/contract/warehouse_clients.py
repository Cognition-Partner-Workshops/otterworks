from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "consumers" / "contract-kit"))
from contract_client import execute as execute_contract  # noqa: E402


class ContractWarehouse(Protocol):
    def execute(self, sql: str, parameters: list[str | None]) -> dict[str, Any]: ...


class EmulatorWarehouse:
    def execute(self, sql: str, parameters: list[str | None]) -> dict[str, Any]:
        from app.warehouse.teradata import SQL

        if sql != SQL:
            raise ValueError("unknown invoice contract query")
        return execute_contract(sql, ROOT, "invoice-export", parameters)


class SnowflakeWarehouse:
    DATABASE = "SFX_D1110_AFTER"
    SCHEMA = "COMPAT"
    QUERY_TAG = '{"run":"sfx-d1110","act":"consumers","consumer":"billing-service"}'

    def execute(self, sql: str, parameters: list[str | None]) -> dict[str, Any]:
        credentials = {
            key: os.getenv(f"SNOWFLAKE_{key}")
            for key in ("ACCOUNT", "USER", "ROLE", "WAREHOUSE", "PRIVATE_KEY")
        }
        if not all(credentials.values()):
            raise ValueError("Snowflake environment not configured")
        raise NotImplementedError(
            "Snowflake adapter not installed; execute supplied DAL SQL in "
            f"{self.DATABASE}.{self.SCHEMA} with QUERY_TAG={self.QUERY_TAG}"
        )


class ContractConnection:
    def __init__(self, warehouse: ContractWarehouse):
        self.warehouse = warehouse
        self.result: dict[str, Any] = {}
        self.parameters: list[str | None] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def cursor(self):
        return self

    def execute(self, sql: str, parameters: list[str | None]):
        self.parameters = parameters
        self.result = self.warehouse.execute(sql, parameters)

    def fetchall(self):
        return self.result["rows"]
