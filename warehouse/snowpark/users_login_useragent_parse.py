"""Preserve the legacy users_login_useragent_parse Python parsing semantics."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render

from snowflake.snowpark.functions import call_udf, col


def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."USERS_LOGIN_USERAGENT_PARSE_BROWSER"'
    session.sql(fr"""
        create or replace temporary function {function}(agent varchar)
        returns varchar
        language python
        runtime_version = '3.10'
        handler = 'browser'
        as $$
import re

def browser(agent):
    match = re.search(r"(Chrome|Firefox|Safari)/(\S+)", agent or "")
    return match.group(1) + "/" + match.group(2) if match else "Other"
$$
    """).collect()
    source = session.table([database, "SPARK_RAW_USERS", "LOGIN_EVENT"])
    result = source.select(
        "LOGIN_EVENT_ID", "USER_ID", "EVENT_AT", "IP_ADDRESS", "USER_AGENT", "RAW_LINE",
        call_udf(function, col("USER_AGENT")).alias("BROWSER"),
    )
    result.write.save_as_table(
        [database, "MART_SPARK", "USERS_LOGIN_USERAGENT_PARSE"],
        mode="overwrite",
        copy_grants=True,
        comment=_run_render("__RUN_TOKEN__ Python parsing output for users_login_useragent_parse."),
    )
