"""Snowpark port of the pkg_analytics Script Task "SCR Row checksum".

The C# task reads event_id, event_type, user_id, resource_id and occurred_at from the staging
table after the load, joins them with "|", hashes the UTF-8 bytes with SHA-256 and writes the
upper-case hex digest to row_checksum. Staging models are views, so the procedure returns the
(event_id, row_checksum) pairs it would have written instead of updating a table.
"""

PROCEDURE = "SSIS_PKG_ANALYTICS"

DDL = """
CREATE OR REPLACE PROCEDURE {qualified_name}()
RETURNS TABLE (EVENT_ID VARCHAR, ROW_CHECKSUM VARCHAR)
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
COMMENT = 'Replaces SSIS pkg_analytics Script Task SCR Row checksum'
AS
$$
import hashlib

from snowflake.snowpark.types import StringType, StructField, StructType

FIELDS = ("EVENT_ID", "EVENT_TYPE", "USER_ID", "RESOURCE_ID", "OCCURRED_AT")


def _text(value):
    return "" if value is None else str(value)


def run(session):
    rows = session.table("{database}.STAGING.STG_ANALYTICS_EVENTS").select(*FIELDS)
    checksums = []
    for row in rows.to_local_iterator():
        payload = "|".join(_text(row[field]) for field in FIELDS)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()
        checksums.append((row["EVENT_ID"], digest))
    schema = StructType(
        [StructField("EVENT_ID", StringType()), StructField("ROW_CHECKSUM", StringType())]
    )
    return session.create_dataframe(checksums, schema=schema)
$$
"""
