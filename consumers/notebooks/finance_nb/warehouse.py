"""Lazy warehouse connection and dataframe query port."""
import os
from pathlib import Path
import tomllib
from typing import Protocol

import pandas as pd

from .databricks_queries import native_sql, pin_teradata

TARGETS = {"teradata", "teradata-emulator", "databricks"}


class WarehouseUnavailable(RuntimeError):
    pass


class Connection(Protocol):
    def cursor(self): ...
    def close(self): ...


class _ResultCursor:
    def __init__(self, execute):
        self._execute = execute
        self.description = None
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        result = self._execute(sql)
        self.description = [(column,) for column in result["columns"]]
        self._rows = [tuple(row) for row in result["rows"]]

    def fetchall(self):
        return self._rows


class EmulatorConnection:
    """Old read path: Teradata SQL through the contract-kit Teradata emulator bridge."""
    dialect = "teradata"

    def __init__(self, as_of=None):
        self.as_of = as_of

    def prepare(self, sql, name=None):
        return pin_teradata(sql, self.as_of)

    def cursor(self):
        from contract.warehouse import execute_contract, ROOT
        return _ResultCursor(lambda sql: execute_contract(sql, ROOT, "notebook"))

    def close(self):
        pass


class DatabricksConnection:
    """New read path: native Databricks SQL through the consumer transport."""
    dialect = "databricks"

    def __init__(self, as_of=None, step="notebook"):
        self.as_of, self.step = as_of, step

    def prepare(self, sql, name=None):
        if name is None:
            raise ValueError("databricks target needs the query name")
        return native_sql(name, self.as_of)

    def cursor(self):
        from .databricks_warehouse import execute
        return _ResultCursor(lambda sql: execute(sql, step=self.step))

    def close(self):
        pass


def connect(config=None, *, connector=None, target=None, as_of=None) -> Connection:
    if os.getenv("FINANCE_WAREHOUSE_ENABLED", "true").lower() not in {"true", "1", "yes"}:
        raise RuntimeError("finance warehouse is disabled")
    target = target or os.getenv("FINANCE_WAREHOUSE", "teradata")
    as_of = as_of or os.getenv("FINANCE_AS_OF") or None
    if target not in TARGETS:
        raise ValueError(f"unknown finance warehouse target: {target}")
    if target == "teradata-emulator":
        return EmulatorConnection(as_of)
    if target == "databricks":
        return DatabricksConnection(as_of)
    if config is None:
        with Path(__file__).with_name("teradata.toml").open("rb") as source:
            config = tomllib.load(source)["connection"]
    try:
        if connector is None:
            import teradatasql
            connector = teradatasql.connect
        return connector(**config)
    except Exception as error:
        raise WarehouseUnavailable("finance warehouse unavailable") from error


def run_query(connection: Connection, sql: str, name: str | None = None) -> pd.DataFrame:
    native = isinstance(connection, (EmulatorConnection, DatabricksConnection))
    statement = connection.prepare(sql, name) if native else sql
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement)
            columns = [item[0] for item in cursor.description]
            return pd.DataFrame.from_records(cursor.fetchall(), columns=columns)
    except Exception as error:
        raise WarehouseUnavailable("finance query failed") from error
