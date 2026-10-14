"""Snowpark port of the pkg_files Script Task "SCR Convert sizes to MB".

The C# task runs after the data flow and, in batches of 5000, sets
`size_mb = ROUND(size_bytes / 1048576.0, 3)` on every stg.stg_files row whose size_mb is
missing or stale. In Snowflake the staging model is a view over RAW.EXT_FILES, so the procedure
returns the converted sizes for every file instead of updating a table; `stg_files.size_mb` must
equal its output row for row.
"""

PROCEDURE = "SSIS_PKG_FILES"

DDL = """
CREATE OR REPLACE PROCEDURE {qualified_name}()
RETURNS TABLE (ID VARCHAR, SIZE_BYTES NUMBER(19, 0), SIZE_MB NUMBER(18, 3))
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
COMMENT = 'Replaces SSIS pkg_files Script Task SCR Convert sizes to MB'
AS
$$
from snowflake.snowpark import functions as F
from snowflake.snowpark.types import DecimalType

BYTES_PER_MB = 1048576
HALF_MB = BYTES_PER_MB // 2


def run(session):
    files = session.table("{database}.RAW.EXT_FILES")
    size_bytes = F.when(F.col("SIZE_BYTES") != F.lit(""), F.col("SIZE_BYTES")).cast(
        DecimalType(19, 0)
    )
    # ROUND(x, 3) half away from zero on non-negative sizes, in exact integer arithmetic:
    # floor((bytes * 1000 + 2^19) / 2^20) / 1000.
    thousandths = F.floor((size_bytes * F.lit(1000) + F.lit(HALF_MB)) / F.lit(BYTES_PER_MB))
    return files.select(
        F.col("ID").cast("VARCHAR").alias("ID"),
        size_bytes.alias("SIZE_BYTES"),
        (thousandths / F.lit(1000)).cast(DecimalType(18, 3)).alias("SIZE_MB"),
    )
$$
"""
