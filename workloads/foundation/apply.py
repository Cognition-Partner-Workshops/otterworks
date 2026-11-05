"""Apply the versioned workload foundation with an attributed Snowflake session."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

import snowflake.connector
import structlog
import yaml
from schemachange.config.ChangeHistoryTable import ChangeHistoryTable
from schemachange.config.DeployConfig import DeployConfig
from schemachange.deploy import deploy
from schemachange.JinjaTemplateProcessor import JinjaTemplateProcessor
from schemachange.session.Script import get_all_scripts_recursively
from schemachange.session.SnowflakeSession import SnowflakeSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "attribution"))
import sf_attribution as sf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HISTORY_DATABASE = f"DB_SCHEMACHANGE_{sf.RUN_TOKEN}"
SESSION_URL = "https://partner-workshops.devinenterprise.com/sessions/6f05f95b4d0f47b5bda7614bd35e4776"
LOGGER = structlog.wrap_logger(
    logging.getLogger(__name__), wrapper_class=structlog.make_filtering_bound_logger(logging.INFO)
)


class AttributedSession(SnowflakeSession):
    def reset_query_tag(self, logger, extra_tag=None):
        pass


def connection_parameters(workload: str, *, admin: bool = False) -> dict:
    ep = sf.endpoint(sf.workload_csids(workload)[0])
    params = sf.connection_params(
        ep, phase="dev", account=os.environ["SNOWFLAKE_EXT_ACCOUNT"],
        private_key_file=os.environ["SNOWFLAKE_EXT_PRIVATE_KEY_FILE"],
        commit=sf.resolve_commit(repo=str(ROOT.parent)), run_id=sf.make_run_id(workload, "dev"),
        session_url=SESSION_URL, role="ACCOUNTADMIN" if admin else "DEVIN_EXT_ROLE",
    )
    params.update(user=os.environ["SNOWFLAKE_EXT_USER"], database=None, schema=None,
                  warehouse=os.environ["SNOWFLAKE_EXT_WAREHOUSE"])
    return params


def new_session(params: dict, history: ChangeHistoryTable) -> AttributedSession:
    connector = snowflake.connector.connect

    def connect(**kwargs):
        kwargs["session_parameters"] = dict(params["session_parameters"])
        kwargs["application"] = sf.APPLICATION
        return connector(**kwargs)

    with patch("schemachange.session.SnowflakeSession.snowflake.connector.connect", side_effect=connect):
        session = AttributedSession(
            schemachange_version="4.4.0", application=sf.APPLICATION, logger=LOGGER,
            change_history_table=history, **{k: v for k, v in params.items() if k != "application"},
        )
    session.session_parameters = dict(params["session_parameters"])
    return session


def template_vars(workload: str) -> dict:
    return {
        "database": sf.database_name(workload), "warehouse": sf.warehouse_name(workload),
        "comment": sf.sql_string(sf.external_comment(workload=workload)),
        "shared_comment": sf.sql_string(sf.external_comment(purpose="foundation governance")),
        "tag": sf.TAG_FQN, "tag_value": sf.sql_string(sf.devin_csid_value(sf.workload_csids(workload))),
        "reader": f"{sf.RUN_TOKEN}_READER", "analyst": f"{sf.RUN_TOKEN}_ANALYST",
    }


def bootstrap_sql() -> str:
    return (f"CREATE DATABASE IF NOT EXISTS {HISTORY_DATABASE} COMMENT = "
            f"{sf.sql_string(sf.external_comment(purpose='migration history'))};")


def migration_jobs(admin: bool):
    entries = yaml.safe_load((ROOT / "index.yaml").read_text())["workloads"]
    if admin:
        return [(entries[0]["id"], ROOT / "foundation" / "admin_migrations", "ADMIN_MONITORS")]
    return [(e["id"], ROOT / e["id"] / "migrations", e["id"].upper()) for e in entries]


def render(folder: Path, variables: dict):
    processor = JinjaTemplateProcessor(project_root=folder, modules_folder=None)
    scripts = get_all_scripts_recursively(root_directory=folder, version_number_regex=None)
    for script in sorted(scripts.values(), key=lambda s: s.name):
        yield script.name, processor.render(processor.relpath(script.file_path), variables)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--admin", action="store_true", help="Apply monitor approvals as ACCOUNTADMIN")
    args = parser.parse_args(argv)
    if version("schemachange") != "4.4.0":
        raise RuntimeError("schemachange==4.4.0 is required")
    bootstrapped = False
    for workload, folder, table in migration_jobs(args.admin):
        history = ChangeHistoryTable(table_name=table, schema_name="CHANGE_HISTORY", database_name=HISTORY_DATABASE)
        variables = template_vars(workload)
        if args.dry_run:
            if not bootstrapped:
                print(bootstrap_sql())
                bootstrapped = True
            print(f"-- Change history: {history.fully_qualified}")
            for name, sql in render(folder, variables):
                print(f"-- {name}\n{sql}")
            continue
        session = new_session(connection_parameters(workload, admin=args.admin), history)
        try:
            if not bootstrapped:
                session.execute_snowflake_query(bootstrap_sql(), logger=LOGGER)
                bootstrapped = True
            config = DeployConfig(root_folder=folder, change_history_table=history,
                                  create_change_history_table=True, config_vars=variables)
            deploy(config=config, session=session)
        finally:
            session.con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
