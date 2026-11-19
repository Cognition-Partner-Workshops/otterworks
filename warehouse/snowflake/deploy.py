"""Deploy versioned plumbing migrations without persisting credentials."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render

import json
import logging
from pathlib import Path
import tempfile

import structlog
import yaml

from sfx_conn import ROOT, WORKLOADS, connect, query_tag
from governance import reapply


def render_migrations(destination):
    paths = [ROOT / 'schemachange-config.yml', *sorted((ROOT / 'migrations').glob('V*.sql'))]
    for path in paths:
        output = destination / path.relative_to(ROOT)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(_run_render(path.read_text()))
    return destination / 'schemachange-config.yml'


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
            cur.execute(_run_render("CREATE SCHEMA IF NOT EXISTS __RUN_DATABASE__.SCHEMACHANGE COMMENT='__RUN_TOKEN__ migration history'"))
            cur.execute(_run_render("""
                CREATE TABLE IF NOT EXISTS __RUN_DATABASE__.SCHEMACHANGE.CHANGE_HISTORY (
                    VERSION VARCHAR, DESCRIPTION VARCHAR, SCRIPT VARCHAR,
                    SCRIPT_TYPE VARCHAR, CHECKSUM VARCHAR, EXECUTION_TIME NUMBER,
                    STATUS VARCHAR, INSTALLED_BY VARCHAR, INSTALLED_ON TIMESTAMP_LTZ
                ) COMMENT='__RUN_TOKEN__ migration history'
            """))
    target = ROOT.parent / 'dbt/target'
    target.mkdir(exist_ok=True)
    rendered = tempfile.TemporaryDirectory(prefix=_run_render('__RUN_TOKEN__')+'-deploy-',dir=target)
    rendered_root = Path(rendered.name)
    config_path = render_migrations(rendered_root)
    config_data = yaml.safe_load(config_path.read_text())
    config = DeployConfig.factory(
        config_file_path=config_path,
        root_folder=rendered_root / config_data["root-folder"],
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
    session.database = _run_render("__RUN_DATABASE__")
    session.schema = "SCHEMACHANGE"
    session.con.autocommit(False)
    try:
        deploy(config, session)
        with session.con.cursor() as cursor:
            reapply(cursor)
    finally:
        session.con.close()
        rendered.cleanup()


if __name__ == "__main__":
    main()
