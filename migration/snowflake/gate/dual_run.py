"""Run the legacy replay, Snowflake build, and parity gate for one date."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def run_step(name: str, command: list[str], environment: dict[str, str]) -> int:
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    elapsed = time.monotonic() - started
    print(f"STEP {name} exit={result.returncode} elapsed={elapsed:.2f}s", flush=True)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"sfm-\d{8}-[a-z0-9]{2,8}", args.run):
        print("run token does not look like sfm-<yyyymmdd>-<suffix>", file=sys.stderr)
        return 2
    try:
        date.fromisoformat(args.date)
    except ValueError:
        print("--date must be an ISO date", file=sys.stderr)
        return 2
    replay = ROOT / "migration" / "snowflake" / "source" / "replay" / "agent_replay.py"
    if not replay.is_file():
        print(f"SQL Server replay script is not available: {replay}", file=sys.stderr)
        return 2

    environment = os.environ.copy()
    environment["UBW_RUN"] = args.run
    commands = (
        ("replay", [sys.executable, str(replay), "--date", args.date]),
        (
            "dbt-build",
            [
                sys.executable,
                str(ROOT / "migration/snowflake/target/python/dbt_env.py"),
                "--",
                "build",
                "--vars",
                f"{{business_date: {args.date}}}",
            ],
        ),
        (
            "parity",
            [
                sys.executable,
                str(HERE / "parity.py"),
                "--run",
                args.run,
                "--date",
                args.date,
            ],
        ),
    )
    for name, command in commands:
        exit_status = run_step(name, command, environment)
        if exit_status:
            return exit_status
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
