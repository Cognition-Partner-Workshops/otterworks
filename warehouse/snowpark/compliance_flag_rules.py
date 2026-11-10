"""Replaces the Spark lake output audit/compliance_flag_rules."""
from snowflake.snowpark.functions import call_udf, col, coalesce, lit

DISPOSITION_HANDLER = """
def disposition(status, severity):
    if status == "closed":
        return "resolved"
    if (severity or 0) >= 7000:
        return "review"
    return "monitor"
"""


def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."COMPLIANCE_FLAG_RULES_DISPOSITION"'
    session.sql(f"""
        create or replace temporary function {function}(status varchar, severity number(10, 0))
        returns varchar
        language python
        runtime_version = '3.10'
        handler = 'disposition'
        as $$
{DISPOSITION_HANDLER}
$$
    """).collect()
    flags = session.table([database, "SPARK_RAW_AUDIT", "COMPLIANCE_FLAG"])
    severity = coalesce(col("SEVERITY"), lit(0)).cast("number(10, 0)")
    result = flags.select(
        coalesce(col("COMPLIANCE_FLAG_ID"), lit(0)).cast("number(19, 0)").alias("FLAG_ID"),
        coalesce(col("DOCUMENT_ID"), lit(0)).cast("number(19, 0)").alias("DOCUMENT_ID"),
        severity.alias("SEVERITY"),
        call_udf(function, col("STATUS"), severity).alias("DISPOSITION"),
    )
    result.write.save_as_table(
        [database, "MART_SPARK", "COMPLIANCE_FLAG_RULES"],
        mode="overwrite",
        comment="sfx-d1110 Replaces the Spark lake output audit/compliance_flag_rules.",
    )
