"""Provision and deploy the doc_usage_dashboard Streamlit in Snowflake app (warehouse runtime).

  provision  as the admin identity (DEVIN_EXT_ROLE): app role, key-pair service user, grants.
  deploy     as the service user: stage, upload, CREATE STREAMLIT on WH_DOC_USAGE_DASHBOARD, DEVIN_CSID tag.

Environment: SNOWFLAKE_ACCOUNT; admin key via SNOWFLAKE_ADMIN_USER + SNOWFLAKE_ADMIN_PRIVATE_KEY_PATH;
service-user key via SNOWFLAKE_PRIVATE_KEY_PATH_CS_DOC_USAGE_DASHBOARD_ACCOUNT_USAGE; DEVIN_SESSION_URL for dev tags.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "attribution"))

import sf_attribution as sf  # noqa: E402

WORKLOAD = "doc_usage_dashboard"
EP = sf.endpoint(sf.workload_csids(WORKLOAD)[0])
DB = sf.database_name(WORKLOAD)
SCHEMA = f"{DB}.{sf.APP_SCHEMA}"
TABLE = f"{SCHEMA}.ACCOUNT_STORAGE_USAGE"
APP = sf.streamlit_name(WORKLOAD)
STAGE = f"{SCHEMA}.{WORKLOAD.upper()}_APP_STAGE"
APP_ROLE = f"{sf.RUN_TOKEN}_{WORKLOAD.upper()}_APP"
VIEWER_ROLE = f"{sf.RUN_TOKEN}_{WORKLOAD.upper()}_VIEWER"
READER_ROLE = f"{sf.RUN_TOKEN}_READER"
ADMIN_ROLE = "DEVIN_EXT_ROLE"
APP_FILES = ("streamlit_app.py", "dashboard.py", "environment.yml")


def provision_sql(rsa_public_key: str) -> list[str]:
    role_comment = sf.sql_string(sf.external_comment(workload=WORKLOAD, csid=EP.csid))
    return [
        f"CREATE ROLE IF NOT EXISTS {APP_ROLE} COMMENT = {role_comment}",
        f"CREATE ROLE IF NOT EXISTS {VIEWER_ROLE} COMMENT = {role_comment}",
        f"GRANT ROLE {READER_ROLE} TO ROLE {APP_ROLE}",
        f"GRANT USAGE ON DATABASE {DB} TO ROLE {APP_ROLE}",
        f"GRANT USAGE ON SCHEMA {SCHEMA} TO ROLE {APP_ROLE}",
        f"GRANT SELECT ON TABLE {TABLE} TO ROLE {APP_ROLE}",
        f"GRANT USAGE ON WAREHOUSE {EP.warehouse} TO ROLE {APP_ROLE}",
        f"GRANT CREATE STAGE, CREATE STREAMLIT ON SCHEMA {SCHEMA} TO ROLE {APP_ROLE}",
        f"GRANT APPLY ON TAG {sf.TAG_FQN} TO ROLE {APP_ROLE}",
        f"GRANT USAGE ON DATABASE {sf.TAG_DATABASE} TO ROLE {APP_ROLE}",
        f"GRANT USAGE ON SCHEMA {sf.TAG_DATABASE}.{sf.TAG_SCHEMA} TO ROLE {APP_ROLE}",
        f"GRANT USAGE ON DATABASE {DB} TO ROLE {VIEWER_ROLE}",
        f"GRANT USAGE ON SCHEMA {SCHEMA} TO ROLE {VIEWER_ROLE}",
        sf.service_user_ddl(EP, rsa_public_key=rsa_public_key, role=APP_ROLE),
        f"ALTER USER {EP.service_user} SET RSA_PUBLIC_KEY = {sf.sql_string(_key_body(rsa_public_key))}",
        f"GRANT ROLE {APP_ROLE} TO USER {EP.service_user}",
    ]


def deploy_sql(stage_dir: str) -> list[str]:
    comment = sf.sql_string(sf.external_comment(csid=EP.csid))
    tag_value = sf.sql_string(sf.devin_csid_value(sf.workload_csids(WORKLOAD)))
    put = [
        f"PUT 'file://{Path(stage_dir, name).as_posix()}' @{STAGE} AUTO_COMPRESS = FALSE OVERWRITE = TRUE"
        for name in sorted(os.listdir(stage_dir))
    ]
    return [
        f"CREATE STAGE IF NOT EXISTS {STAGE} DIRECTORY = (ENABLE = TRUE) COMMENT = {comment}",
        *put,
        f"CREATE OR REPLACE STREAMLIT {APP} FROM '@{STAGE}' MAIN_FILE = 'streamlit_app.py'"
        f" QUERY_WAREHOUSE = {EP.warehouse} TITLE = 'Storage quota per account' COMMENT = {comment}",
        f"ALTER STREAMLIT {APP} ADD LIVE VERSION FROM LAST",
        f"ALTER STREAMLIT {APP} SET TAG {sf.TAG_FQN} = {tag_value}",
        f"GRANT USAGE ON STREAMLIT {APP} TO ROLE {VIEWER_ROLE}",
    ]


def runtime_config(commit: str, run_id: str) -> dict[str, str]:
    return {
        "table": TABLE,
        "query_tag": sf.query_tag_json(EP, phase="runtime", commit=commit, run_id=run_id),
        "query_tag_sql": sf.streamlit_session_tag_sql(EP, commit=commit, run_id=run_id),
    }


def build_stage_dir(target: str, commit: str, run_id: str) -> None:
    for name in APP_FILES:
        src = HERE / "app" / name
        if src.exists():
            shutil.copy(src, Path(target, name))
    Path(target, "runtime_config.json").write_text(json.dumps(runtime_config(commit, run_id), indent=2) + "\n")


def _key_body(pem: str) -> str:
    return "".join(line.strip() for line in pem.strip().splitlines() if not line.startswith("-----"))


def _run(conn, statements: list[str]) -> None:
    cur = conn.cursor()
    for statement in statements:
        print(">>", statement if "RSA_PUBLIC_KEY" not in statement else statement.split(" RSA_PUBLIC_KEY")[0] + " ...")
        cur.execute(statement)
        for row in cur.fetchall()[:5]:
            print("  ", row)


def _admin_connection(commit: str):
    params = sf.connection_params(
        EP,
        phase="dev",
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        private_key_file=os.environ["SNOWFLAKE_ADMIN_PRIVATE_KEY_PATH"],
        commit=commit,
        run_id=sf.make_run_id(WORKLOAD, "dev"),
        session_url=os.environ["DEVIN_SESSION_URL"],
        role=ADMIN_ROLE,
    )
    params["user"] = os.environ["SNOWFLAKE_ADMIN_USER"]
    import snowflake.connector

    return snowflake.connector.connect(**params)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("provision", "deploy", "print"))
    parser.add_argument("--public-key", help="PEM public key file for the service user (provision)")
    parser.add_argument("--commit")
    parser.add_argument("--runtime-run-id")
    args = parser.parse_args(argv)
    commit = sf.resolve_commit(args.commit, repo=str(HERE))
    run_id = args.runtime_run_id or sf.make_run_id(WORKLOAD, "runtime")

    if args.step == "print":
        with tempfile.TemporaryDirectory() as stage_dir:
            build_stage_dir(stage_dir, commit, run_id)
            for statement in deploy_sql(stage_dir):
                print(statement)
        return 0
    if args.step == "provision":
        if not args.public_key:
            parser.error("provision needs --public-key")
        with _admin_connection(commit) as conn:
            _run(conn, provision_sql(Path(args.public_key).read_text()))
        return 0
    os.environ.setdefault("SNOWFLAKE_ROLE", APP_ROLE)
    with tempfile.TemporaryDirectory() as stage_dir:
        build_stage_dir(stage_dir, commit, run_id)
        with sf.connect(EP, "dev") as conn:
            _run(conn, deploy_sql(stage_dir))
    print("runtime run_id:", run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
