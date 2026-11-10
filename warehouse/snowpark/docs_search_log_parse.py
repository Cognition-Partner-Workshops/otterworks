"""Preserve the legacy docs_search_log_parse Python parsing semantics."""
from snowflake.snowpark.functions import call_udf, col


def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."DOCS_SEARCH_LOG_PARSE_PARSE_ACTION"'
    session.sql(fr"""
        create or replace temporary function {function}(line varchar)
        returns varchar
        language python
        runtime_version = '3.10'
        handler = 'parse_action'
        as $$
import re

def parse_action(line):
    match = re.search(r"action=(\w+)", line or "")
    return match.group(1) if match else None
$$
    """).collect()
    source = session.table([database, "SPARK_RAW_DOCUMENTS", "SEARCH_INDEX_LOG"])
    result = source.select(
        "SEARCH_INDEX_LOG_ID", "DOCUMENT_ID", "EVENT_AT", "RAW_LINE", "STATUS",
        call_udf(function, col("RAW_LINE")).alias("PARSED_ACTION"),
    )
    result.write.save_as_table(
        [database, "MART_SPARK", "DOCS_SEARCH_LOG_PARSE"],
        mode="overwrite",
        comment="sfx-d1110 Python parsing output for docs_search_log_parse.",
    )
