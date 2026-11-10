"""Deploy versioned plumbing migrations without persisting credentials."""
import json
import logging

import structlog
import yaml

from sfx_conn import ROOT, WORKLOADS, connect, query_tag
from governance import reapply


def redact_connection_fields(logger, method, event):
    for field in ("snowflake_account", "default_role"):
        if field in event:
            event[field] = "[redacted]"
    return event


def main():
    from schemachange.config.DeployConfig import DeployConfig
    from schemachange.deploy import deploy
    from schemachange.session.SnowflakeSession import SnowflakeSession

    class JWTSession(SnowflakeSession):
        def reset_query_tag(self, logger, extra_tag=None):
            with self.con.cursor() as cur:
                cur.execute("ALTER SESSION SET QUERY_TAG = %s",
                            (self.session_parameters["QUERY_TAG"],))

    tag = query_tag("ops", "deploy")
    structlog.configure(
        processors=[redact_connection_fields, structlog.processors.KeyValueRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
    variables = json.loads(tag)
    variables["run_id"] = "scheduled"
    with connect("ops", "bootstrap") as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS SFX_D1110_AFTER.SCHEMACHANGE COMMENT='sfx-d1110 migration history'")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS SFX_D1110_AFTER.SCHEMACHANGE.CHANGE_HISTORY (
                    VERSION VARCHAR, DESCRIPTION VARCHAR, SCRIPT VARCHAR,
                    SCRIPT_TYPE VARCHAR, CHECKSUM VARCHAR, EXECUTION_TIME NUMBER,
                    STATUS VARCHAR, INSTALLED_BY VARCHAR, INSTALLED_ON TIMESTAMP_LTZ
                ) COMMENT='sfx-d1110 migration history'
            """)
    config_data = yaml.safe_load((ROOT / "schemachange-config.yml").read_text())
    config = DeployConfig.factory(
        config_file_path=ROOT / "schemachange-config.yml",
        root_folder=ROOT / config_data["root-folder"],
        change_history_table=config_data["change-history-table"],
        create_change_history_table=config_data["create-change-history-table"],
        config_vars=variables, query_tag=tag,
    )
    # Use the existing in-memory JWT connection; schemachange 4 expects a key file.
    session = JWTSession.__new__(JWTSession)
    session.con = connect("ops", "deploy", schema="SCHEMACHANGE")
    session.change_history_table = config.change_history_table
    session.autocommit = False
    session.logger = structlog.get_logger()
    session.session_parameters = {"QUERY_TAG": tag}
    session.account = session.con.account
    session.user = session.con.user
    session.role = session.con.role
    session.warehouse = WORKLOADS["ops"]
    session.database = "SFX_D1110_AFTER"
    session.schema = "SCHEMACHANGE"
    session.con.autocommit(False)
    try:
        deploy(config, session)
        with session.con.cursor() as cursor:
            reapply(cursor)
    finally:
        session.con.close()


if __name__ == "__main__":
    main()
