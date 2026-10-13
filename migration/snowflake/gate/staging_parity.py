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

A package that lands several tables lists them under `destinations:` instead, each entry with
its own sqlserver_table, snowflake_model, keys, columns, rename and excluded; each is a unit
`ssis:<package>:<table>`.

It writes `gate/out/staging/<package>.json` and `.md`, appends the row to
`OPS.PARITY_LEDGER` with the unit `ssis:<package>`, and prints
`Staging parity <package> <STATUS> <source rows> / <target rows>`. A DIVERGE needs an
`Explanation:` line in the markdown, which carries forward like the manifest ledger, and a
`### Business decisions` section at the end of the markdown is kept across runs.
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
DESTINATION_KEYS = SPEC_KEYS - {"package"}
DECISIONS_HEADING = "### Business decisions"


def _destination(entry: dict[str, Any], label: str) -> dict[str, Any]:
    missing = sorted(DESTINATION_KEYS - set(entry))
    if missing:
        raise ValueError(f"{label} is missing {', '.join(missing)}")
    overlap = set(entry["keys"]) & set(entry["columns"])
    if overlap:
        raise ValueError(f"{label} lists {sorted(overlap)} as both keys and columns")
    destination = {key: entry[key] for key in DESTINATION_KEYS}
    destination["rename"] = entry.get("rename") or {}
    destination["excluded"] = entry.get("excluded") or {}
    return destination


def load_spec(package: str, spec_dir: Path = SPEC_DIR) -> dict[str, Any]:
    path = spec_dir / f"{package}.yaml"
    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if spec.get("package") != package:
        raise ValueError(f"{path.name} names package {spec.get('package')!r}")
    if "destinations" in spec:
        entries = spec["destinations"] or []
        if not entries:
            raise ValueError(f"{path.name} has an empty destinations list")
        destinations = [
            _destination(entry, f"{path.name} destination {index}")
            for index, entry in enumerate(entries)
        ]
        for destination in destinations:
            table = parity.source_parts(destination["sqlserver_table"])[1]
            destination["unit"] = f"ssis:{package}:{table}"
    else:
        destinations = [_destination(spec, path.name)]
        destinations[0]["unit"] = f"ssis:{package}"
    return {"package": package, "destinations": destinations}


def target_name(destination: dict[str, Any], column: str) -> str:
    return str(destination["rename"].get(column, column))


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


def _decisions_section(markdown_path: Path) -> list[str]:
    if not markdown_path.is_file():
        return []
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() == DECISIONS_HEADING:
            return lines[index:]
    return []


def write_result(
    output_dir: Path,
    run: str,
    business_date: str,
    spec: dict[str, Any],
    units: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    package = spec["package"]
    markdown_path = output_dir / f"{package}.md"
    previous = parity.read_explanations(markdown_path)
    decisions = _decisions_section(markdown_path)
    for unit in units:
        unit["explanation"] = previous.get(unit["unit"], "") if unit["status"] == "DIVERGE" else ""
    payload = {
        "run": run,
        "date": business_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "spec": spec,
        "units": units,
    }
    (output_dir / f"{package}.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    lines = [summary_line(unit) for unit in units]
    for destination, unit in zip(spec["destinations"], units, strict=True):
        lines.extend(
            [
                "",
                f"`{unit['unit']}`: SQL Server `{destination['sqlserver_table']}` vs Snowflake "
                f"`{destination['snowflake_model']}`, keys {', '.join(destination['keys'])}, "
                f"{len(destination['columns'])} compared columns.",
            ]
        )
        if destination["excluded"]:
            lines.append("Not compared:")
            lines.extend(
                f"- `{column}`: {reason}" for column, reason in destination["excluded"].items()
            )
    for unit in units:
        if unit["status"] != "DIVERGE":
            continue
        lines.extend(["", f"### {unit['unit']}", ""])
        for difference in unit["differences"]:
            lines.append(
                f"- `{json.dumps(difference['key'], sort_keys=True)}` "
                f"`{difference['column']}`: SQL Server `{difference['sqlserver']}`, "
                f"Snowflake `{difference['snowflake']}`"
            )
        lines.append(f"Explanation: {unit['explanation']}")
    if decisions:
        lines.extend(["", *decisions])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summary_line(unit: dict[str, Any]) -> str:
    return (
        f"Staging parity {unit['unit'].removeprefix('ssis:')} {unit['status']} "
        f"{unit['source_rows']} / {unit['target_rows']} "
        f"differing_keys={unit['differing_key_count']}"
    )


def pending(unit_name: str) -> dict[str, Any]:
    return {
        "unit": unit_name,
        "status": "PENDING",
        "source_rows": 0,
        "target_rows": 0,
        "differing_key_count": 0,
        "differences": [],
        "explanation": "",
    }


def run_staging_gate(
    run: str,
    package: str,
    business_date: str,
    output_dir: Path,
    spec_dir: Path = SPEC_DIR,
    record: bool = True,
) -> int:
    parity.validate_run(run)
    date.fromisoformat(business_date)
    spec = load_spec(package, spec_dir)
    prefix = parity.object_prefix(run)
    units: list[dict[str, Any]] = []
    with parity.dbt_connection(run) as target_connection, target_connection.cursor() as cursor:
        source_connection = parity.connect_source_database()
        try:
            for destination in spec["destinations"]:
                schema, relation = parity.relation_parts(destination["snowflake_model"])
                if not parity.target_exists(cursor, prefix, schema, relation):
                    units.append(pending(destination["unit"]))
                    continue
                source = fetch_source(source_connection, destination)
                target = fetch_target(cursor, prefix, destination)
                result = comparison.compare_frames(
                    source, target, destination["keys"], destination["columns"]
                )
                units.append(parity.result_dict(destination["unit"], result))
        finally:
            source_connection.close()
        write_result(output_dir, run, business_date, spec, units)
        if record:
            parity.record_ledger(target_connection, run, business_date, units)
    for unit in units:
        print(summary_line(unit))
    return parity.exit_code(units)


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
