"""Preserve the legacy docs_tag_normalize Python parsing semantics."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render

from snowflake.snowpark.functions import call_udf, col


def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."DOCS_TAG_NORMALIZE_NORMALIZE"'
    session.sql(fr"""
        create or replace temporary function {function}(tag varchar)
        returns varchar
        language python
        runtime_version = '3.10'
        handler = 'normalize'
        as $$
import re

def normalize(tag):
    return re.sub(r"\s+", "-", (tag or "").strip().lower())
$$
    """).collect()
    source = session.table([database, "SPARK_RAW_DOCUMENTS", "DOC_TAG"])
    result = source.select(
        "DOC_TAG_ID", "DOCUMENT_ID", "TAG",
        call_udf(function, col("TAG")).alias("NORMALIZED_TAG"),
    )
    result.write.save_as_table(
        [database, "MART_SPARK", "DOCS_TAG_NORMALIZE"],
        mode="overwrite",
        comment=_run_render("__RUN_TOKEN__ Python parsing output for docs_tag_normalize."),
    )
