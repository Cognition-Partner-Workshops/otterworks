"""Run one job module with the shared, tagged Snowpark session."""
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
            session.sql(f"ALTER TABLE {relation} SET TAG {database}.GOVERNANCE.SFX_RUN = 'sfx-d1110'").collect()
            token = os.environ.get("SNOWFLAKE_RUN_TOKEN", "sfx-d1110")
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            session.sql(f"COMMENT ON TABLE {relation} IS ?",
                        params=[token + ' Spark output ' + job]).collect()
            return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    run(parser.parse_args().job)
