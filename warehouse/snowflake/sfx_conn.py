"""JWT connections and consistent workload attribution."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render
from warehouse.sql import compose, identifier
from warehouse.run_config import RunConfig

import json
import os
import re
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from warehouse.query_tags import query_tag as session_tag

ROOT = Path(__file__).resolve().parent
WORKLOADS = yaml.safe_load(_run_render((ROOT / "workloads.yml").read_text()))


def query_tag(workload, phase, extra=None, job=None):
    if workload not in WORKLOADS:
        raise ValueError(f"Unknown workload: {workload}")
    tag = {
        "executed_by": os.environ.get("SFX_EXECUTED_BY", "manual"),
        "built_with": os.environ.get("SFX_BUILT_WITH", "devin"),
    }
    tag.update(extra or {})
    job = job or os.environ.get("SFX_SPARK_JOB")
    if job is not None:
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", job):
            raise ValueError("Invalid Spark job identifier")
        tag.update(run=_run_render("__RUN_TOKEN__"), act="spark", job=job)
    return session_tag(workload, phase, tag)


def connect(workload, phase, extra_tag=None, job=None, **kw):
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    tag = query_tag(workload, phase, extra_tag, job=job)
    key = serialization.load_pem_private_key(
        os.environ["SNOWFLAKE_PRIVATE_KEY"].encode(), password=None
    )
    params = dict(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        role=os.environ["SNOWFLAKE_ROLE"], database=os.environ.get("SNOWFLAKE_DATABASE", RunConfig.from_env().database),
        application="Cognition_Devin",
        warehouse=WORKLOADS[workload], authenticator="SNOWFLAKE_JWT",
        private_key=key.private_bytes(serialization.Encoding.DER,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()),
    )
    session = dict(kw.pop("session_parameters", {}))
    session["QUERY_TAG"] = tag
    session["TIMEZONE"] = "UTC"
    params.update(kw)
    if json.loads(tag).get("act") == "spark":
        if params["database"] != _run_render("__RUN_DATABASE__") or params["warehouse"] not in WORKLOADS.values():
            raise ValueError(_run_render("Spark act requires __RUN_DATABASE__ and a run-scoped warehouse"))
    params["session_parameters"] = session
    return snowflake.connector.connect(**params)


def suspend_all():
    from snowflake.connector.errors import ProgrammingError

    with connect("ops", "suspend") as conn:
        with conn.cursor() as cur:
            for warehouse in WORKLOADS.values():
                try:
                    cur.execute(compose('ALTER WAREHOUSE {} SUSPEND', identifier(warehouse)))
                    print(f"{warehouse}: suspended")
                except ProgrammingError as error:
                    if "already suspended" not in str(error).lower():
                        if error.errno != 90064:
                            raise
                        cur.execute('SHOW WAREHOUSES LIKE %s', (warehouse,))
                        columns = [column[0] for column in cur.description]
                        states = [dict(zip(columns, row)) for row in cur.fetchall()]
                        if len(states) != 1 or states[0]["state"] != "SUSPENDED":
                            raise
                    print(f"{warehouse}: already suspended")


if __name__ == "__main__":
    suspend_all()
