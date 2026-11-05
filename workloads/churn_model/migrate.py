"""Apply only the churn workload's versioned migrations, using an in-memory admin key."""

import argparse
import os
from pathlib import Path
from unittest.mock import patch

import snowflake.connector
from cryptography.hazmat.primitives import serialization
from schemachange.config.ChangeHistoryTable import ChangeHistoryTable
from schemachange.config.DeployConfig import DeployConfig
from schemachange.deploy import deploy

from workloads.churn_model.provision import EP, admin_connection, params, sf
from workloads.foundation.apply import HISTORY_DATABASE, new_session, render, template_vars


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    folder = Path(__file__).with_name("migrations")
    variables = template_vars(EP.workload)
    if args.dry_run:
        for name, sql in render(folder, variables):
            print(f"-- {name}\n{sql}")
        return
    # Reuse the migration history and session semantics without file-based credentials.
    key = serialization.load_pem_private_key(os.environ["SNOWFLAKE_EXT_PRIVATE_KEY"].encode(), password=None)
    parameters = params(key, sf.make_run_id(EP.workload, "dev"), sf.resolve_commit(), "DEVIN_EXT_ROLE")
    parameters["user"] = os.environ["SNOWFLAKE_EXT_USER"]
    history = ChangeHistoryTable(table_name="CHURN_MODEL", schema_name="CHANGE_HISTORY", database_name=HISTORY_DATABASE)
    with admin_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {HISTORY_DATABASE} COMMENT = {variables['shared_comment']}")
    connector = snowflake.connector.connect

    def connect(**kwargs):
        kwargs["private_key"] = parameters["private_key"]
        return connector(**kwargs)

    with patch("snowflake.connector.connect", side_effect=connect):
        session = new_session(parameters, history)
    try:
        deploy(config=DeployConfig(root_folder=folder, change_history_table=history,
                                   create_change_history_table=True, config_vars=variables), session=session)
    finally:
        session.con.close()


if __name__ == "__main__":
    main()
