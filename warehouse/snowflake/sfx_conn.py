"""JWT connections and consistent workload attribution."""
import json
import os
from pathlib import Path
import subprocess
import uuid

import yaml

ROOT = Path(__file__).resolve().parent
WORKLOADS = yaml.safe_load((ROOT / "workloads.yml").read_text())
RUN_ID = os.environ.get("SFX_RUN_ID") or str(uuid.uuid4())


def query_tag(workload, phase):
    if workload not in WORKLOADS:
        raise ValueError(f"Unknown workload: {workload}")
    commit = os.environ.get("SFX_COMMIT")
    if not commit:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    return json.dumps({
        "workload": workload, "phase": phase, "commit": commit,
        "run_id": os.environ.get("SFX_RUN_ID", RUN_ID),
        "run_token": os.environ.get("SNOWFLAKE_RUN_TOKEN", "sfx-d1110"),
        "executed_by": os.environ.get("SFX_EXECUTED_BY", "manual"),
        "built_with": os.environ.get("SFX_BUILT_WITH", "devin"),
    }, separators=(",", ":"))


def connect(workload, phase, **kw):
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    tag = query_tag(workload, phase)
    key = serialization.load_pem_private_key(
        os.environ["SNOWFLAKE_PRIVATE_KEY"].encode(), password=None
    )
    params = dict(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        role=os.environ["SNOWFLAKE_ROLE"], database=os.environ["SNOWFLAKE_DATABASE"],
        warehouse=WORKLOADS[workload], authenticator="SNOWFLAKE_JWT",
        private_key=key.private_bytes(serialization.Encoding.DER,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()),
    )
    session = dict(kw.pop("session_parameters", {}))
    session["QUERY_TAG"] = tag
    session["TIMEZONE"] = "UTC"
    params.update(kw)
    params["session_parameters"] = session
    return snowflake.connector.connect(**params)


def suspend_all():
    from snowflake.connector.errors import ProgrammingError

    with connect("ops", "suspend") as conn:
        with conn.cursor() as cur:
            for warehouse in WORKLOADS.values():
                try:
                    cur.execute(f"ALTER WAREHOUSE {warehouse} SUSPEND")
                    print(f"{warehouse}: suspended")
                except ProgrammingError as error:
                    if "already suspended" not in str(error).lower():
                        if error.errno != 90064:
                            raise
                        cur.execute(f"SHOW WAREHOUSES LIKE '{warehouse}'")
                        columns = [column[0] for column in cur.description]
                        states = [dict(zip(columns, row)) for row in cur.fetchall()]
                        if len(states) != 1 or states[0]["state"] != "SUSPENDED":
                            raise
                    print(f"{warehouse}: already suspended")


if __name__ == "__main__":
    suspend_all()
