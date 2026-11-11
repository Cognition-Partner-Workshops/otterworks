"""Run one job module with the shared, tagged Snowpark session."""
import argparse
import importlib.util
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
            return module.run(session)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    run(parser.parse_args().job)
