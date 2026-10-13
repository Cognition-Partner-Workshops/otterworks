"""Snowpark port of etl/scripts/capacity_forecast_weekly.py (cron `15 6 * * 1`).

The legacy job reads mart.mart_capacity_forecast_input for a business date (the latest one when
none is given), fits a least-squares line through each tenant's (observation_date, bytes_used)
points, predicts bytes_used 30 days after the business date, truncates to a whole byte and floors
at zero, then writes forecast_bytes_30d and forecast_generated_at (UTC) onto the tenant's row whose
observation_date is the business date. The handler below is the same arithmetic in the same
order, so both backends produce the same integers from the same input rows; it updates
MARTS.BUILD_CAPACITY_FORECAST_INPUT, the dbt model that replaces the mart table.

`etl/scripts/capacity_forecast_weekly.py` calls it with `UBW_BACKEND=snowflake`, and the
UBW_WEEKLY_CAPACITY_FORECAST task calls it after rebuilding the input.
"""

PROCEDURE = "UBW_CAPACITY_FORECAST_WEEKLY"

DDL = """
CREATE OR REPLACE PROCEDURE {qualified_name}(BUSINESS_DATE DATE)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
COMMENT = 'Replaces the cron job etl/scripts/capacity_forecast_weekly.py'
EXECUTE AS OWNER
AS
$$
import json
from collections import defaultdict

TABLE = "{database}.MARTS.BUILD_CAPACITY_FORECAST_INPUT"


def forecast(values, business_date):
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


def run(session, business_date):
    if business_date is None:
        business_date = session.sql(f"SELECT MAX(BUSINESS_DATE) FROM {TABLE}").collect()[0][0]
        if business_date is None:
            raise ValueError("The warehouse has no capacity forecast input rows")
    rows = session.sql(
        f"SELECT TENANT_ID, OBSERVATION_DATE, BYTES_USED FROM {TABLE} "
        "WHERE BUSINESS_DATE = ? ORDER BY TENANT_ID, OBSERVATION_DATE",
        params=[business_date],
    ).collect()
    by_tenant = defaultdict(list)
    for row in rows:
        by_tenant[str(row[0])].append((row[1], int(row[2])))
    forecasts = [
        (tenant_id, forecast(observations, business_date))
        for tenant_id, observations in by_tenant.items()
    ]
    if forecasts:
        # Owner's-rights procedures cannot create temporary tables, so the batch travels as JSON.
        payload = json.dumps([{"t": tenant, "f": value} for tenant, value in forecasts])
        session.sql(
            f"UPDATE {TABLE} AS target "
            "SET FORECAST_BYTES_30D = batch.FORECAST_BYTES_30D, "
            "FORECAST_GENERATED_AT = SYSDATE() "
            "FROM (SELECT f.value:t::VARCHAR AS TENANT_ID, "
            "f.value:f::NUMBER(38, 0) AS FORECAST_BYTES_30D "
            "FROM TABLE(FLATTEN(INPUT => PARSE_JSON(?))) AS f) AS batch "
            "WHERE target.TENANT_ID = batch.TENANT_ID "
            "AND target.BUSINESS_DATE = ? AND target.OBSERVATION_DATE = ?",
            params=[payload, business_date, business_date],
        ).collect()
    return (
        f"Forecasted {len(forecasts)} tenants for {business_date}: "
        f"{len(rows)} observations, 30-day horizon"
    )
$$
"""
