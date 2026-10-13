"""Write 30-day capacity forecasts to the Snowflake forecast-input model."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date

from snowflake.snowpark import Session
from snowflake.snowpark.functions import max as max_


def _forecast(values: list[tuple[date, int]], business_date: date) -> int:
    points = [(observation.toordinal(), float(amount)) for observation, amount in values]
    mean_x = sum(point[0] for point in points) / len(points)
    mean_y = sum(point[1] for point in points) / len(points)
    denominator = sum((point[0] - mean_x) ** 2 for point in points)
    slope = (
        sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator if denominator else 0.0
    )
    prediction = mean_y + slope * (business_date.toordinal() + 30 - mean_x)
    return max(0, int(prediction))


def run_forecast(session: Session, business_date: date | None) -> str:
    forecast_input = session.table("MARTS.BUILD_CAPACITY_FORECAST_INPUT")
    if business_date is None:
        selected = forecast_input.select(max_("BUSINESS_DATE")).collect()
        if not selected or selected[0][0] is None:
            raise RuntimeError("The warehouse has no capacity forecast input rows")
        business_date = selected[0][0]

    rows = (
        forecast_input.filter(forecast_input["BUSINESS_DATE"] == business_date)
        .select("TENANT_ID", "OBSERVATION_DATE", "BYTES_USED")
        .sort("TENANT_ID", "OBSERVATION_DATE")
        .collect()
    )
    by_tenant: dict[str, list[tuple[date, int]]] = defaultdict(list)
    for row in rows:
        by_tenant[str(row["TENANT_ID"])].append((row["OBSERVATION_DATE"], int(row["BYTES_USED"])))

    forecasts = {
        tenant_id: _forecast(observations, business_date)
        for tenant_id, observations in by_tenant.items()
    }
    for tenant_id, forecast_bytes in forecasts.items():
        session.sql(
            """
            UPDATE MARTS.BUILD_CAPACITY_FORECAST_INPUT
            SET FORECAST_BYTES_30D = ?,
                FORECAST_GENERATED_AT =
                    CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())::TIMESTAMP_NTZ
            WHERE BUSINESS_DATE = ?
              AND TENANT_ID = ?
              AND OBSERVATION_DATE = ?
            """,
            params=[forecast_bytes, business_date, tenant_id, business_date],
        ).collect()

    return (
        f"Forecasted {len(forecasts)} tenants for {business_date}: "
        f"{len(rows)} observations, 30-day horizon"
    )


def run(session: Session, business_date: date) -> str:
    return run_forecast(session, business_date)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--business-date", type=date.fromisoformat)
    args = parser.parse_args(argv)
    try:
        from ubw_snowflake import dbt_snowpark_session, validate_run

        validate_run(args.run)
        session = dbt_snowpark_session(args.run)
        try:
            print(run_forecast(session, args.business_date))
        finally:
            session.close()
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
