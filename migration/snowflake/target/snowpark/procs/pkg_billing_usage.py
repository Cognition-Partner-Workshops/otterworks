"""Snowpark port of pkg_billing_usage's Script Task "SCR Read usage watermark".

The C# task reads ops.parity_watermarks.watermark_value for 'pkg_billing_usage' into
User::WatermarkFrom (1900-01-01 when unset); the data flow then appends only events with
occurred_at > WatermarkFrom, and "SQL Update usage watermark" saves
CONVERT(nvarchar(64), MAX(occurred_at), 126) of the staging table. In Snowflake the saved
state is the incremental model STAGING.STG_BILLING_USAGE_EVENTS itself, so the procedure
derives the same watermark from it and returns it in SQL Server style-126 text.
"""

PROCEDURE = "SSIS_PKG_BILLING_USAGE"

DDL = """
CREATE OR REPLACE PROCEDURE {qualified_name}(BUSINESS_DATE VARCHAR)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
COMMENT = 'Replaces SSIS pkg_billing_usage Script Task SCR Read usage watermark'
AS
$$
from datetime import datetime

DEFAULT_WATERMARK = datetime(1900, 1, 1)


def style_126(value):
    # CONVERT(nvarchar(64), <datetime2(7)>, 126): fraction omitted when zero, else 7 digits.
    text = value.strftime("%Y-%m-%dT%H:%M:%S")
    if value.microsecond:
        text += "." + f"{value.microsecond:06d}" + "0"
    return text


def run(session, business_date):
    row = session.sql(
        "SELECT MAX(occurred_at) AS watermark, COUNT(*) AS loaded_rows "
        "FROM {database}.STAGING.STG_BILLING_USAGE_EVENTS"
    ).collect()[0]
    saved = row["WATERMARK"]
    watermark_from = saved if saved is not None else DEFAULT_WATERMARK
    return {
        "object_name": "pkg_billing_usage",
        "watermark_column": "occurred_at",
        "watermark_value": style_126(saved) if saved is not None else None,
        "watermark_from": style_126(watermark_from),
        "business_date": business_date,
        "loaded_rows": row["LOADED_ROWS"],
    }
$$
"""
