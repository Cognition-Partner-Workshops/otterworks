"""Operate-session connections and dbt environment from the local named profile."""
import json
import os
from pathlib import Path

import tomlkit


def query_tag(step):
    return json.dumps({"run": "sfx-d1110", "act": "operate", "step": step}, separators=(",", ":"))


def connect(step, warehouse, connector=None):
    if not warehouse.startswith("SFX_D1110_"):
        raise ValueError("warehouse must be scoped to SFX_D1110_")
    if connector is None:
        import snowflake.connector
        connector = snowflake.connector.connect
    return connector(connection_name="sfx_d1110", database="SFX_D1110_AFTER",
                     warehouse=warehouse,
                     session_parameters={"QUERY_TAG": query_tag(step), "TIMEZONE": "UTC"})


def dbt_env(config_path=None):
    path = config_path or Path.home() / ".snowflake/connections.toml"
    config = tomlkit.parse(Path(path).read_text())["sfx_d1110"]
    if config["database"] != "SFX_D1110_AFTER":
        raise ValueError("operate requires SFX_D1110_AFTER")
    env = os.environ.copy()
    for key in ("account", "user", "role", "database"):
        env["SNOWFLAKE_" + key.upper()] = config[key]
    env["DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY"] = Path(config["private_key_file"]).expanduser().read_text()
    env["SNOWFLAKE_TRANSFORM_WAREHOUSE"] = "SFX_D1110_TRANSFORM_WH"
    env["SNOWFLAKE_SCHEMA"] = "CORE_BILLING"
    env["SFX_QUERY_TAG"] = query_tag("dbt_build")
    env["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"
    return env
