#!/usr/bin/env python3
"""Write a 30-day storage forecast back to the warehouse input rows.

UBW_BACKEND selects the warehouse: `sqlserver` (default) runs the forecast here against
mart.mart_capacity_forecast_input; `snowflake` calls the Snowpark port
OPS.UBW_CAPACITY_FORECAST_WEEKLY in the run's database (UBW_RUN), which does the same arithmetic
on MARTS.BUILD_CAPACITY_FORECAST_INPUT. The Snowflake login is the run's DBT user with its key
pair (SNOWFLAKE_PRIVATE_KEY or UBW_DBT_PRIVATE_KEY), SNOWFLAKE_ACCOUNT and optional SNOWFLAKE_HOST.
"""

from __future__ import annotations

import argparse
import os
import re
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


RUN_PATTERN = re.compile(r"^sfm-\d{8}-[a-z0-9]{2,8}$")


def _snowflake_prefix(run: str) -> str:
    if not RUN_PATTERN.fullmatch(run):
        raise RuntimeError(f"UBW_RUN {run!r} does not look like sfm-<yyyymmdd>-<suffix>")
    return "OW_UBW_" + run.upper().replace("-", "_")


def _snowflake_private_key() -> bytes:
    from cryptography.hazmat.primitives import serialization

    pem = os.environ.get("SNOWFLAKE_PRIVATE_KEY") or os.environ.get("UBW_DBT_PRIVATE_KEY", "")
    if not pem:
        raise RuntimeError("SNOWFLAKE_PRIVATE_KEY (or UBW_DBT_PRIVATE_KEY) is not set")
    body = "".join(re.sub(r"-----(BEGIN|END) PRIVATE KEY-----", "", pem).split())
    lines = [body[index : index + 64] for index in range(0, len(body), 64)]
    header = "-----BEGIN PRIVATE KEY-----"  # gitleaks:allow
    pem_text = "\n".join([header, *lines, "-----END PRIVATE KEY-----", ""])
    key = serialization.load_pem_private_key(pem_text.encode(), password=None)
    return key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def run_snowflake_forecast(business_date: date | None) -> int:
    import snowflake.connector

    prefix = _snowflake_prefix(os.environ.get("UBW_RUN", ""))
    params: dict[str, Any] = {
        "account": os.environ.get("SNOWFLAKE_ACCOUNT", ""),
        "user": os.environ.get("UBW_DBT_USER", f"{prefix}_DBT"),
        "private_key": _snowflake_private_key(),
        "role": f"{prefix}_ENGINEER",
        "warehouse": f"{prefix}_WH",
        "database": prefix,
        "schema": "OPS",
    }
    if not params["account"]:
        raise RuntimeError("SNOWFLAKE_ACCOUNT is not set")
    if os.environ.get("SNOWFLAKE_HOST"):
        params["host"] = os.environ["SNOWFLAKE_HOST"]
    with snowflake.connector.connect(**params) as connection, connection.cursor() as cursor:
        cursor.execute(
            f"CALL {prefix}.OPS.UBW_CAPACITY_FORECAST_WEEKLY(%s::DATE)",  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            (business_date.isoformat() if business_date else None,),
        )
        result = cursor.fetchone()
    print(result[0] if result else "UBW_CAPACITY_FORECAST_WEEKLY returned nothing")
    return 0


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
        return run_snowflake_forecast(args.business_date)
    if backend != "sqlserver":
        print(f"Unknown UBW_BACKEND: {backend}", file=sys.stderr)
        return 2
    return run_forecast(args.business_date)


if __name__ == "__main__":
    raise SystemExit(main())
