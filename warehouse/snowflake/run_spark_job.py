"""Dispatch a migrated registration without coupling job-specific commands."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def run(job):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", job):
        raise ValueError("Invalid job identifier")
    entry = json.loads((ROOT / "etl/spark/jobs/registry" / f"{job}.yaml").read_text())
    if entry["status"] != "snowflake" or not entry.get("command", "").strip():
        raise ValueError("Job must have snowflake status and a command")
    env = {**os.environ, "SFX_SPARK_JOB": job}
    # Commands are reviewed repository code, never caller-provided shell text.
    # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
    return subprocess.run(entry["command"], shell=True, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    run(parser.parse_args().job)
