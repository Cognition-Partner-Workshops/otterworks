"""Compare one SSIS package's SQL Server staging table with its Snowflake staging model.

The manifest gate compares procedures. This compares what a package lands in `stg` with the
dbt staging model that replaces the package, using the spec in `gate/staging/<package>.yaml`:

    package: pkg_files
    sqlserver_table: stg.stg_files
    snowflake_model: STAGING.STG_FILES
    keys: [id]                      # SQL Server column names
    columns: [name, size_mb, ...]   # SQL Server column names compared on every row
    rename: {id: file_id}           # optional, SQL Server name -> Snowflake column name
    excluded: {extracted_at: "run timestamp"}  # columns not compared, with the reason

It writes `gate/out/staging/<package>.json` and `.md`, appends the row to
`OPS.PARITY_LEDGER` with the unit `ssis:<package>`, and prints
`Staging parity <package> <STATUS> <source rows> / <target rows>`. A DIVERGE needs an
`Explanation:` line in the markdown, which carries forward like the manifest ledger.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "target" / "python")]
parity = importlib.import_module("parity")
comparison = importlib.import_module("compare")

SPEC_DIR = HERE / "staging"
OUT_DIR = HERE / "out" / "staging"
SPEC_KEYS = {"package", "sqlserver_table", "snowflake_model", "keys", "columns"}


def load_spec(package: str, spec_dir: Path = SPEC_DIR) -> dict[str, Any]:
    path = spec_dir / f"{package}.yaml"
    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    missing = sorted(SPEC_KEYS - set(spec))
    if missing:
        raise ValueError(f"{path.name} is missing {', '.join(missing)}")
    if spec["package"] != package:
        raise ValueError(f"{path.name} names package {spec['package']!r}")
    overlap = set(spec["keys"]) & set(spec["columns"])
    if overlap:
        raise ValueError(f"{path.name} lists {sorted(overlap)} as both keys and columns")
    spec.setdefault("rename", {})
    spec.setdefault("excluded", {})
    return spec


def target_name(spec: dict[str, Any], column: str) -> str:
    return str(spec["rename"].get(column, column))


def fetch_source(connection: Any, spec: dict[str, Any]) -> pd.DataFrame:
    schema, table = parity.source_parts(spec["sqlserver_table"])
    columns = [*spec["keys"], *spec["columns"]]
    select_list = ", ".join(f"[{column}]" for column in columns)
    with connection.cursor(as_dict=False) as cursor:
        cursor.execute(f"SELECT {select_list} FROM [{schema}].[{table}]")  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
        rows = cursor.fetchall()
    return pd.DataFrame(rows, columns=columns)


def fetch_target(cursor: Any, database: str, spec: dict[str, Any]) -> pd.DataFrame:
    schema, relation = parity.relation_parts(spec["snowflake_model"])
    columns = [*spec["keys"], *spec["columns"]]
    select_list = ", ".join(f'"{target_name(spec, column).upper()}"' for column in columns)
    cursor.execute(f'SELECT {select_list} FROM "{database}"."{schema}"."{relation}"')  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
    return pd.DataFrame(cursor.fetchall(), columns=columns)


def write_result(output_dir: Path, run: str, business_date: str, spec: dict[str, Any],
                 unit: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    package = spec["package"]
    markdown_path = output_dir / f"{package}.md"
    previous = parity.read_explanations(markdown_path)
    unit_name = unit["unit"]
    unit["explanation"] = previous.get(unit_name, "") if unit["status"] == "DIVERGE" else ""
    payload = {
        "run": run,
        "date": business_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "spec": spec,
        "unit": unit,
    }
    (output_dir / f"{package}.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    lines = [
        summary_line(unit),
        "",
        f"SQL Server `{spec['sqlserver_table']}` vs Snowflake `{spec['snowflake_model']}`, "
        f"keys {', '.join(spec['keys'])}, {len(spec['columns'])} compared columns.",
    ]
    if spec["excluded"]:
        lines.append("")
        lines.append("Not compared:")
        lines.extend(f"- `{column}`: {reason}" for column, reason in spec["excluded"].items())
    if unit["status"] == "DIVERGE":
        lines.extend(["", f"### {unit_name}", ""])
        for difference in unit["differences"]:
            lines.append(
                f"- `{json.dumps(difference['key'], sort_keys=True)}` "
                f"`{difference['column']}`: SQL Server `{difference['sqlserver']}`, "
                f"Snowflake `{difference['snowflake']}`"
            )
        lines.append(f"Explanation: {unit['explanation']}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summary_line(unit: dict[str, Any]) -> str:
    return (
        f"Staging parity {unit['unit'].removeprefix('ssis:')} {unit['status']} "
        f"{unit['source_rows']} / {unit['target_rows']} "
        f"differing_keys={unit['differing_key_count']}"
    )


def run_staging_gate(run: str, package: str, business_date: str, output_dir: Path,
                     spec_dir: Path = SPEC_DIR, record: bool = True) -> int:
    parity.validate_run(run)
    date.fromisoformat(business_date)
    spec = load_spec(package, spec_dir)
    prefix = parity.object_prefix(run)
    unit_name = f"ssis:{package}"
    with parity.dbt_connection(run) as target_connection, target_connection.cursor() as cursor:
        schema, relation = parity.relation_parts(spec["snowflake_model"])
        if not parity.target_exists(cursor, prefix, schema, relation):
            unit = {"unit": unit_name, "status": "PENDING", "source_rows": 0, "target_rows": 0,
                    "differing_key_count": 0, "differences": [], "explanation": ""}
        else:
            source_connection = parity.connect_source_database()
            try:
                source = fetch_source(source_connection, spec)
            finally:
                source_connection.close()
            target = fetch_target(cursor, prefix, spec)
            result = comparison.compare_frames(source, target, spec["keys"], spec["columns"])
            unit = parity.result_dict(unit_name, result)
        write_result(output_dir, run, business_date, spec, unit)
        if record:
            parity.record_ledger(target_connection, run, business_date, [unit])
    print(summary_line(unit))
    if unit["status"] == "PENDING":
        return 1
    if unit["status"] == "DIVERGE" and not unit["explanation"].strip():
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--date", default="2026-09-30",
                        help="business date the package was replayed for")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--no-record", action="store_true",
                        help="do not append the row to OPS.PARITY_LEDGER")
    args = parser.parse_args()
    try:
        return run_staging_gate(args.run, args.package, args.date, args.out,
                                record=not args.no_record)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
