from __future__ import annotations

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
        from teradata_reference import SQL

        if sql != SQL:
            raise ValueError("unknown invoice contract query")
        return execute_contract(sql, ROOT, "invoice-export", parameters)


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
