"""Run one job module with the shared, tagged Snowpark session."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render

import argparse
import importlib.util
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "snowflake"))
from sfx_conn import connect, query_tag


def run(job):
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", job) or job == "run_job":
        raise ValueError("Invalid job identifier")
    path = ROOT / f"{job}.py"
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(f"spark_job_{job}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from snowflake.snowpark import Session

    with connect("snowpark", "spark-job", job=job) as connection:
        with Session.builder.configs({"connection": connection}).create() as session:
            session.query_tag = query_tag("snowpark", "spark-job", job=job)
            result = module.run(session)
            database = session.get_current_database()
            relation = f'{database}."MART_SPARK"."{job.upper()}"'
            # Database comes from Snowpark (quoted); job is validated above.
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            session.sql(_run_render(f"ALTER TABLE {relation} SET TAG {database}.GOVERNANCE.SFX_RUN = '__RUN_TOKEN__'")).collect()
            token = os.environ.get("RUN_TOKEN", _run_render("__RUN_TOKEN__"))
            # The shared connector uses pyformat, while Session.sql params require qmark.
            with connection.cursor() as cursor:
                # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
                cursor.execute(f"COMMENT ON TABLE {relation} IS %s",
                               (token + ' Spark output ' + job,))
            return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    run(parser.parse_args().job)
