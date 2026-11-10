"""Lazy warehouse connection and dataframe query port."""
import os
from pathlib import Path
import tomllib
from typing import Protocol

import pandas as pd


class WarehouseUnavailable(RuntimeError):
    pass


class Connection(Protocol):
    def cursor(self): ...
    def close(self): ...


def connect(config=None, *, connector=None) -> Connection:
    if os.getenv("FINANCE_WAREHOUSE_ENABLED", "true").lower() not in {"true", "1", "yes"}:
        raise RuntimeError("finance warehouse is disabled")
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


def run_query(connection: Connection, sql: str) -> pd.DataFrame:
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            columns = [item[0] for item in cursor.description]
            return pd.DataFrame.from_records(cursor.fetchall(), columns=columns)
    except Exception as error:
        raise WarehouseUnavailable("finance query failed") from error
