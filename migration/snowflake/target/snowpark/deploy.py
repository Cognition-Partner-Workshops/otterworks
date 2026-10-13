"""Create the Snowpark procedures that replace SSIS Script Tasks in the run database.

Every module in `procs/` defines `PROCEDURE` (the procedure name, created in `<run db>.OPS`)
and `DDL`, a `CREATE OR REPLACE PROCEDURE` statement in which `{qualified_name}` and
`{database}` are substituted at deploy time. One module per package keeps the package
families independent of each other.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "python"))

from ubw_snowflake import dbt_connection, object_prefix, validate_run  # noqa: E402

PROCS = HERE / "procs"


def load_modules(directory: Path = PROCS) -> list[ModuleType]:
    modules = []
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"sfm_proc_{path.stem}", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for attribute in ("PROCEDURE", "DDL"):
            if not isinstance(getattr(module, attribute, None), str):
                raise RuntimeError(f"{path.name} must define {attribute} as a string")
        modules.append(module)
    return modules


def render(module: ModuleType, database: str) -> str:
    qualified = f"{database}.OPS.{module.PROCEDURE}"
    return module.DDL.replace("{qualified_name}", qualified).replace("{database}", database)


def deploy(run: str, only: str | None = None) -> None:
    validate_run(run)
    database = object_prefix(run)
    modules = [m for m in load_modules() if only in (None, m.PROCEDURE)]
    if only and not modules:
        raise RuntimeError(f"no procedure named {only} in {PROCS}")
    with dbt_connection(run) as connection, connection.cursor() as cursor:
        for module in modules:
            cursor.execute(render(module, database))  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            print(f"PROCEDURE         {database}.OPS.{module.PROCEDURE}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True)
    parser.add_argument("--only", help="deploy one procedure by name")
    args = parser.parse_args()
    try:
        deploy(args.run, args.only)
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
