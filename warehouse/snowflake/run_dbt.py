"""Run dbt with shared tags and secret-safe profile environment bindings."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render
from warehouse.run_config import RunConfig

import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

from sfx_conn import ROOT, query_tag

SELECTOR = re.compile(r"(?:[0-9]*\+|@)?(?:[a-z_]+(?:\.[a-z_]+)*:)?[A-Za-z0-9_*][A-Za-z0-9_.*/-]*(?:\+[0-9]*)?")
PHASE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
LOAD_DATE = re.compile(r"[0-9]{8}")


def selection(value):
    tokens = value.split()
    if not tokens or not all(SELECTOR.fullmatch(part) for token in tokens for part in token.split(",")):
        raise argparse.ArgumentTypeError("invalid dbt selection: %r" % value)
    return " ".join(tokens)


def phase(value):
    if not PHASE.fullmatch(value):
        raise argparse.ArgumentTypeError("invalid phase: %r" % value)
    return value


def load_date(value):
    if not LOAD_DATE.fullmatch(value):
        raise argparse.ArgumentTypeError("--load-date must be YYYYMMDD")
    return value


def dbt_argv(command, project, target, logs, select=None, variables=None):
    """Build dbt argv from values already validated at the CLI boundary."""
    if command not in ("parse", "build"):
        raise ValueError("unsupported dbt command: %r" % command)
    argv = [str(Path(sys.executable).with_name("dbt")), command,
            "--project-dir", str(project), "--profiles-dir", str(project),
            "--target-path", str(target), "--log-path", str(logs)]
    if command == "build":
        argv += ["--select", selection(select)]
    return argv + ["--vars", json.dumps(variables or {})]


def run(argv, env):
    subprocess.run(argv, env=env, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["parse", "build"])
    parser.add_argument("--phase", type=phase, default="dbt")
    parser.add_argument("--job")
    parser.add_argument("--step")
    parser.add_argument("--mapping")
    parser.add_argument("--select", dest="selection", type=selection, default="staging.billing")
    parser.add_argument("--load-date", type=load_date)
    args = parser.parse_args()
    env = os.environ.copy()
    config = RunConfig.from_env()
    env.update(config.environment())
    env.setdefault("SNOWFLAKE_DATABASE", config.database)
    env.setdefault("SNOWFLAKE_TRANSFORM_WAREHOUSE", config.database + "_TRANSFORM_WH")
    if args.command == "parse":
        for key in ("ACCOUNT", "USER", "ROLE", "DATABASE"):
            env["SNOWFLAKE_" + key] = "offline_dummy"
        env["DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY"] = "offline_dummy"
    else:
        if args.job or env.get("SFX_SPARK_JOB"):
            if env["SNOWFLAKE_DATABASE"] != _run_render("__RUN_DATABASE__") or env.get(
                "SNOWFLAKE_TRANSFORM_WAREHOUSE", _run_render("__RUN_DATABASE___TRANSFORM_WH")
            ) != _run_render("__RUN_DATABASE___TRANSFORM_WH"):
                raise ValueError(_run_render("Spark dbt requires __RUN_DATABASE__ and __RUN_DATABASE___TRANSFORM_WH"))
        env["DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY"] = env["SNOWFLAKE_PRIVATE_KEY"]
    extra = ({"run": _run_render("__RUN_TOKEN__"), "act": "scale", "step": args.step} if args.step else {})
    if args.mapping:
        extra["mapping"] = args.mapping
    tag = json.loads(query_tag("transform", args.phase, extra, job=args.job))
    env["SFX_QUERY_TAG"] = json.dumps(tag, separators=(",", ":"))
    env["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"
    source_project = ROOT.parent / "dbt"
    target = source_project / 'target'
    target.mkdir(exist_ok=True)
    rendered = tempfile.TemporaryDirectory(prefix=config.token+'-',dir=target)
    project = Path(rendered.name)
    for path in source_project.rglob('*'):
        relative = path.relative_to(source_project)
        if path.is_file() and relative.parts[0] in ('models','macros','analyses','seeds','snapshots','dbt_project.yml','profiles.yml'):
            destination = project / relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(config.render(path.read_text()))
    variables = {"phase": args.phase}
    if args.load_date:
        variables["load_date"] = args.load_date
    command = dbt_argv(args.command, project, target, source_project / 'logs', args.selection, variables)
    try:
        run(command, env)
    finally:
        rendered.cleanup()


if __name__ == "__main__":
    main()
