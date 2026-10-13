"""Run dbt with the selected run's key-pair profile."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ubw_snowflake import normalise_pem, object_prefix, validate_run

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent / "dbt"


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] != "--":
        print("usage: dbt_env.py -- <dbt arguments>", file=sys.stderr)
        return 2
    run = os.environ.get("UBW_RUN", "")
    try:
        validate_run(run)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    private_pem = os.environ.get("SNOWFLAKE_PRIVATE_KEY", "")
    if not private_pem:
        print("SNOWFLAKE_PRIVATE_KEY is not set", file=sys.stderr)
        return 2
    prefix = object_prefix(run)
    if not os.environ.get("UBW_DBT_USER"):
        os.environ["UBW_DBT_USER"] = f"{prefix}_DBT"
    os.environ["UBW_DBT_PRIVATE_KEY"] = normalise_pem(private_pem).decode()
    arguments = [
        "dbt",
        *sys.argv[2:],
        "--project-dir",
        str(PROJECT),
        "--profiles-dir",
        str(PROJECT),
    ]
    try:
        os.execvp(arguments[0], arguments)  # nosemgrep: python.lang.security.audit.dangerous-os-exec-tainted-env-args.dangerous-os-exec-tainted-env-args  # noqa: E501
    except FileNotFoundError:
        print("dbt executable is not available on PATH", file=sys.stderr)
        return 127
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
