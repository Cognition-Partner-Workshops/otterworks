"""Replaces the Spark lake output documents/doc_version_diff_stats."""
from snowflake.snowpark import Window
from snowflake.snowpark.functions import call_udf, col, lag


def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."DOC_VERSION_DIFF_STATS_SIMILARITY"'
    session.sql(f"""
        create or replace temporary function {function}(before varchar, after varchar)
        returns float
        language python
        runtime_version = '3.10'
        handler = 'similarity'
        as $$
import difflib

def similarity(before, after):
    return difflib.SequenceMatcher(None, before or "", after or "").ratio()
$$
    """).collect()
    versions = session.table([database, "SPARK_RAW_DOCUMENTS", "DOC_VERSION"])
    previous = lag(col("BODY")).over(
        Window.partition_by("DOCUMENT_ID").order_by("VERSION_NUMBER")
    )
    result = versions.with_column("PREVIOUS_BODY", previous).select(
        "DOC_VERSION_ID", "DOCUMENT_ID", "VERSION_NUMBER", "BODY", "CREATED_AT",
        "PREVIOUS_BODY",
        call_udf(function, col("PREVIOUS_BODY"), col("BODY")).alias("SIMILARITY"),
    )
    result.write.save_as_table(
        [database, "MART_SPARK", "DOC_VERSION_DIFF_STATS"],
        mode="overwrite",
        comment="sfx-d1110 Replaces the Spark lake output documents/doc_version_diff_stats.",
    )
