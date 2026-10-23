#!/usr/bin/env python3
"""Write a 30-day storage forecast back to the warehouse input rows."""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import date
from typing import Any

import pymssql


def _forecast(values: list[tuple[date, int]], business_date: date) -> int:
    points = [(observation.toordinal(), float(amount)) for observation, amount in values]
    mean_x = sum(point[0] for point in points) / len(points)
    mean_y = sum(point[1] for point in points) / len(points)
    denominator = sum((point[0] - mean_x) ** 2 for point in points)
    slope = (
        sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator
        if denominator
        else 0.0
    )
    prediction = mean_y + slope * (business_date.toordinal() + 30 - mean_x)
    return max(0, int(prediction))


def _connect() -> Any:
    return pymssql.connect(
        server=os.environ.get("UBW_SQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("UBW_SQL_PORT", "14333")),
        user=os.environ.get("UBW_SQL_USER", "sa"),
        password=os.environ.get("UBW_SQL_PASSWORD", "OtterUbw_2016dev"),
        database=os.environ.get("UBW_SQL_DATABASE", "OtterWorksUBW"),
        autocommit=True,
    )


def _load_rows(cursor: Any, business_date: date | None) -> tuple[date, list[tuple[Any, ...]]]:
    if business_date is None:
        cursor.execute("SELECT MAX(business_date) FROM mart.mart_capacity_forecast_input")
        result = cursor.fetchone()
        if result is None or result[0] is None:
            raise RuntimeError("The warehouse has no capacity forecast input rows")
        business_date = result[0]
    cursor.execute(
        """
        SELECT tenant_id, observation_date, bytes_used
        FROM mart.mart_capacity_forecast_input
        WHERE business_date = %s
        ORDER BY tenant_id, observation_date
        """,
        (business_date,),
    )
    return business_date, list(cursor.fetchall())


def run_forecast(business_date: date | None) -> int:
    connection = _connect()
    try:
        cursor = connection.cursor()
        selected_date, rows = _load_rows(cursor, business_date)
        by_tenant: dict[str, list[tuple[date, int]]] = defaultdict(list)
        for tenant_id, observation_date, bytes_used in rows:
            by_tenant[str(tenant_id)].append((observation_date, int(bytes_used)))

        forecasts = {
            tenant_id: _forecast(observations, selected_date)
            for tenant_id, observations in by_tenant.items()
        }
        for tenant_id, forecast_bytes in forecasts.items():
            cursor.execute(
                """
                UPDATE mart.mart_capacity_forecast_input
                SET forecast_bytes_30d = %s,
                    forecast_generated_at = SYSUTCDATETIME()
                WHERE business_date = %s
                  AND tenant_id = %s
                  AND observation_date = %s
                """,
                (forecast_bytes, selected_date, tenant_id, selected_date),
            )
        print(
            f"Forecasted {len(forecasts)} tenants for {selected_date}: "
            f"{len(rows)} observations, 30-day horizon"
        )
        cursor.close()
        return 0
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forecast tenant storage for the next 30 days.")
    parser.add_argument("--business-date", type=date.fromisoformat)
    args = parser.parse_args(argv)
    backend = os.environ.get("UBW_BACKEND", "sqlserver").lower()
    if backend == "snowflake":
        raise NotImplementedError("UBW_BACKEND=snowflake is not implemented in the legacy job yet")
    if backend != "sqlserver":
        print(f"Unknown UBW_BACKEND: {backend}", file=sys.stderr)
        return 2
    return run_forecast(args.business_date)


if __name__ == "__main__":
    raise SystemExit(main())
