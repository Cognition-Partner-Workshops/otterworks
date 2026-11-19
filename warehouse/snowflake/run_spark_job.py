"""Dispatch a migrated registration without coupling job-specific commands."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[2]))
from warehouse.run_config import render as _run_render

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def run(job):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", job):
        raise ValueError("Invalid job identifier")
    entry = json.loads(_run_render((ROOT / "etl/spark/jobs/registry" / f"{job}.yaml").read_text()))
    if entry["status"] != "snowflake" or not entry.get("command", "").strip():
        raise ValueError("Job must have snowflake status and a command")
    env = {**os.environ, "SFX_SPARK_JOB": job}
    command = shlex.split(entry['command'])
    if (not command or not re.fullmatch(r'[A-Za-z0-9_./ -]+', command[0])
            or command[0].startswith('-')):
        raise ValueError('Invalid registry executable path')
    return subprocess.run(args=command, shell=False, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    run(parser.parse_args().job)
