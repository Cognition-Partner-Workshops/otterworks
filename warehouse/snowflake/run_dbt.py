"""Run dbt with shared tags and secret-safe profile environment bindings."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from sfx_conn import ROOT, query_tag


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["parse", "build"])
    parser.add_argument("--phase", default="dbt")
    args = parser.parse_args()
    env = os.environ.copy()
    if args.command == "parse":
        for key in ("ACCOUNT", "USER", "ROLE", "DATABASE"):
            env["SNOWFLAKE_" + key] = "offline_dummy"
        env["DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY"] = "offline_dummy"
    else:
        env["DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY"] = env["SNOWFLAKE_PRIVATE_KEY"]
    tag = json.loads(query_tag("transform", args.phase))
    env["SFX_QUERY_TAG"] = json.dumps(tag, separators=(",", ":"))
    env["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"
    project = ROOT.parent / "dbt"
    command = [str(Path(sys.executable).with_name("dbt")), args.command,
               "--project-dir", str(project), "--profiles-dir", str(project)]
    if args.command == "build":
        command += ["--select", "staging.billing"]
    command += ["--vars", json.dumps({"phase": args.phase})]
    subprocess.run(command, env=env, check=True)


if __name__ == "__main__":
    main()
