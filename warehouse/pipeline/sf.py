"""Operate-session connections and dbt environment from the local named profile."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render

import json
import os
from pathlib import Path

import tomlkit


def query_tag(step):
    return json.dumps({"run": _run_render("__RUN_TOKEN__"), "act": "operate", "step": step}, separators=(",", ":"))


def connect(step, warehouse, connector=None):
    if not warehouse.startswith(_run_render("__RUN_DATABASE___")):
        raise ValueError(_run_render("warehouse must be scoped to __RUN_DATABASE___"))
    if connector is None:
        import snowflake.connector
        connector = snowflake.connector.connect
    return connector(connection_name="sfx_d1110", database=_run_render("__RUN_DATABASE__"),
                     warehouse=warehouse,
                     session_parameters={"QUERY_TAG": query_tag(step), "TIMEZONE": "UTC"})


def dbt_env(config_path=None):
    path = config_path or Path.home() / ".snowflake/connections.toml"
    config = tomlkit.parse(_run_render(Path(path).read_text()))["sfx_d1110"]
    if config["database"] != _run_render("__RUN_DATABASE__"):
        raise ValueError(_run_render("operate requires __RUN_DATABASE__"))
    env = os.environ.copy()
    for key in ("account", "user", "role", "database"):
        env["SNOWFLAKE_" + key.upper()] = config[key]
    env["DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY"] = _run_render(Path(config["private_key_file"]).expanduser().read_text())
    env["SNOWFLAKE_TRANSFORM_WAREHOUSE"] = _run_render("__RUN_DATABASE___TRANSFORM_WH")
    env["SNOWFLAKE_SCHEMA"] = "CORE_BILLING"
    env["SFX_QUERY_TAG"] = query_tag("dbt_build")
    env["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"
    return env
