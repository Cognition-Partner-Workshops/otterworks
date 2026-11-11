"""Preserve the legacy user_pref_json_flatten Python parsing semantics."""
from snowflake.snowpark.functions import call_udf, col, lit


def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."USER_PREF_JSON_FLATTEN_PREFERENCE"'
    session.sql(fr"""
        create or replace temporary function {function}(raw varchar, key varchar)
        returns varchar
        language python
        runtime_version = '3.10'
        handler = 'preference'
        as $$
import json

def preference(raw, key):
    try:
        return str(json.loads(raw or "{{}}").get(key, ""))
    except (ValueError, TypeError):
        return None
$$
    """).collect()
    source = session.table([database, "SPARK_RAW_USERS", "USER_PREF"])
    result = source.select("USER_PREF_ID", "USER_ID", "PREF_JSON")
    for key in ("theme", "notifications", "locale"):
        result = result.with_column(
            key.upper(), call_udf(function, col("PREF_JSON"), lit(key))
        )
    result.write.save_as_table(
        [database, "MART_SPARK", "USER_PREF_JSON_FLATTEN"],
        mode="overwrite",
        comment="sfx-d1110 Python parsing output for user_pref_json_flatten.",
    )
