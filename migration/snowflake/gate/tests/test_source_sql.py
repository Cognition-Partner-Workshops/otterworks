from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from migration.snowflake.gate.parity import fetch_source_frame


class InMemoryCursor:
    def __init__(self) -> None:
        self.description = [("business_date",), ("object_name",), ("rows_written",)]
        self.query = ""
        self.parameters: Any = None

    def __enter__(self) -> InMemoryCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, parameters: Any = None) -> None:
        self.query = query
        self.parameters = parameters

    def fetchall(self) -> list[tuple[object, ...]]:
        return [(date(2026, 9, 15), "usp_rollup_audit", 12)]


class InMemoryConnection:
    def __init__(self) -> None:
        self.result_cursor = InMemoryCursor()

    def cursor(self, as_dict: bool = False) -> InMemoryCursor:
        assert not as_dict
        return self.result_cursor


def test_source_sql_executes_with_business_date_parameter() -> None:
    connection = InMemoryConnection()
    source_sql = (
        "SELECT business_date, object_name, rows_written FROM ops.etl_run_log "
        "WHERE business_date = %(business_date)s"
    )
    unit = {
        "keys": ["business_date", "object_name"],
        "columns": ["rows_written"],
        "source_sql": source_sql,
    }

    frame = fetch_source_frame(connection, unit, date(2026, 9, 15))

    assert connection.result_cursor.query == source_sql
    assert connection.result_cursor.parameters == {"business_date": date(2026, 9, 15)}
    assert frame.equals(
        pd.DataFrame(
            [(date(2026, 9, 15), "usp_rollup_audit", 12)],
            columns=["business_date", "object_name", "rows_written"],
        )
    )
