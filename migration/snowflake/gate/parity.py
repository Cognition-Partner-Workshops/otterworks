"""Compare the SQL Server estate with the Snowflake run and write a parity ledger."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pymssql
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(HERE.parent / "target" / "python")]
snowflake_helpers = importlib.import_module("ubw_snowflake")
comparison = importlib.import_module("compare")
dbt_connection = snowflake_helpers.dbt_connection
object_prefix = snowflake_helpers.object_prefix
validate_run = snowflake_helpers.validate_run
UnitResult = comparison.UnitResult
compare_frames = comparison.compare_frames


def load_manifest(path: Path) -> list[dict[str, Any]]:
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    units = content.get("units", [])
    names = [unit["unit"] for unit in units]
    if len(names) != len(set(names)):
        raise ValueError("manifest unit names must be unique")
    return units


def summary_line(units: list[dict[str, Any]]) -> str:
    counts = {status: 0 for status in ("PASS", "DIVERGE", "PENDING")}
    for unit in units:
        counts[unit["status"]] += 1
    return f"Parity PASS={counts['PASS']} DIVERGE={counts['DIVERGE']} PENDING={counts['PENDING']}"


def exit_code(units: list[dict[str, Any]]) -> int:
    if any(unit["status"] == "PENDING" for unit in units):
        return 1
    if any(
        unit["status"] == "DIVERGE" and not unit.get("explanation", "").strip() for unit in units
    ):
        return 1
    return 0


def read_explanations(markdown_path: Path) -> dict[str, str]:
    if not markdown_path.is_file():
        return {}
    explanations: dict[str, str] = {}
    current: str | None = None
    collecting = False
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        heading = re.match(r"^###\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1)
            collecting = False
            continue
        if current is None:
            continue
        if line.startswith("Explanation:"):
            explanations[current] = line.partition(":")[2].strip()
            collecting = True
            continue
        if collecting:
            if line.startswith("### ") or not line.strip():
                collecting = False
            elif line.strip():
                explanations[current] = f"{explanations.get(current, '')} {line.strip()}".strip()
    return explanations


def write_ledger(
    output_dir: Path,
    run: str,
    business_date: str,
    units: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "ledger.md"
    previous = read_explanations(markdown_path)
    for unit in units:
        if unit["status"] == "DIVERGE":
            unit["explanation"] = previous.get(unit["unit"], unit.get("explanation", ""))
        else:
            unit["explanation"] = ""

    generated_at = datetime.now(UTC).isoformat()
    payload = {
        "run": run,
        "date": business_date,
        "generated_at": generated_at,
        "units": units,
    }
    (output_dir / "ledger.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )

    lines = [
        summary_line(units),
        "",
        "| Unit | Status | Rows (SQL Server / Snowflake) | Differing keys |",
        "| --- | --- | ---: | ---: |",
    ]
    for unit in units:
        lines.append(
            f"| {unit['unit']} | {unit['status']} | "
            f"{unit['source_rows']} / {unit['target_rows']} | "
            f"{unit['differing_key_count']} |"
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
        lines.append(f"Explanation: {unit.get('explanation', '')}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def relation_parts(target_model: str) -> tuple[str, str]:
    parts = target_model.split(".")
    if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in parts):
        raise ValueError(f"invalid target model name {target_model!r}")
    return parts[0].upper(), parts[1].upper()


def source_parts(owned_table: str) -> tuple[str, str]:
    parts = owned_table.split(".")
    if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in parts):
        raise ValueError(f"invalid source table name {owned_table!r}")
    return parts[0], parts[1]


def relation_columns(cursor: Any, database: str, schema: str, relation: str) -> set[str]:
    cursor.execute(
        f"""SELECT COLUMN_NAME
        FROM "{database}".INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s""",
        (schema, relation),
    )
    return {str(row[0]).lower() for row in cursor.fetchall()}


def require_columns(unit: str, columns: list[str], available: set[str], side: str) -> None:
    for column in columns:
        if column.lower() not in available:
            raise ValueError(f"{unit}: manifest column {column!r} is missing from {side}")


def target_exists(cursor: Any, database: str, schema: str, relation: str) -> bool:
    cursor.execute(
        f"""SELECT 1
        FROM "{database}".INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
          AND TABLE_TYPE IN ('BASE TABLE', 'VIEW', 'MATERIALIZED VIEW')
        LIMIT 1""",
        (schema, relation),
    )
    return cursor.fetchone() is not None


def fetch_source_frame(connection: Any, unit: dict[str, Any], business_date: date) -> pd.DataFrame:
    schema, table = source_parts(unit["owned_table"])
    columns = [*unit["keys"], *unit["columns"]]
    select_list = ", ".join(f"[{column}]" for column in columns)
    query = f"SELECT {select_list} FROM [{schema}].[{table}]"
    parameters: tuple[Any, ...] = ()
    if unit.get("business_date_column"):
        query += f" WHERE [{unit['business_date_column']}] = %s"
        parameters = (business_date,)
    with connection.cursor(as_dict=False) as cursor:
        cursor.execute(query, parameters)
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
    return pd.DataFrame(rows, columns=column_names)


def fetch_target_frame(
    cursor: Any,
    database: str,
    schema: str,
    relation: str,
    unit: dict[str, Any],
    business_date: date,
) -> pd.DataFrame:
    columns = [*unit["keys"], *unit["columns"]]
    select_list = ", ".join(f'"{column.upper()}"' for column in columns)
    query = f'SELECT {select_list} FROM "{database}"."{schema}"."{relation}"'
    parameters: tuple[Any, ...] = ()
    if unit.get("business_date_column"):
        query += f' WHERE "{unit["business_date_column"].upper()}" = %s'
        parameters = (business_date,)
    cursor.execute(query, parameters)
    rows = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]
    return pd.DataFrame(rows, columns=column_names)


def connect_source_database() -> Any:
    required = ("UBW_SQL_HOST", "UBW_SQL_USER", "UBW_SQL_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"SQL Server comparison requires environment variables: {', '.join(missing)}"
        )
    return pymssql.connect(
        server=os.environ["UBW_SQL_HOST"],
        port=int(os.environ.get("UBW_SQL_PORT", "1433")),
        user=os.environ["UBW_SQL_USER"],
        password=os.environ["UBW_SQL_PASSWORD"],
        database="OtterWorksUBW",
    )


def result_dict(unit_name: str, result: UnitResult) -> dict[str, Any]:
    return {
        "unit": unit_name,
        "status": result.status,
        "source_rows": result.source_rows,
        "target_rows": result.target_rows,
        "differing_key_count": result.differing_key_count,
        "differences": result.differences,
        "explanation": "",
    }


def record_ledger(
    connection: Any, run: str, business_date: str, units: list[dict[str, Any]]
) -> None:
    prefix = object_prefix(run)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""CREATE TABLE IF NOT EXISTS {prefix}.OPS.PARITY_LEDGER (
                RUN_TOKEN VARCHAR,
                BUSINESS_DATE DATE,
                UNIT VARCHAR,
                STATUS VARCHAR,
                SOURCE_ROWS NUMBER,
                TARGET_ROWS NUMBER,
                DIFFERING_KEY_COUNT NUMBER,
                DETAILS VARIANT,
                EXPLANATION VARCHAR,
                GENERATED_AT TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
            )"""
        )
        for unit in units:
            cursor.execute(
                f"""INSERT INTO {prefix}.OPS.PARITY_LEDGER (
                    RUN_TOKEN, BUSINESS_DATE, UNIT, STATUS, SOURCE_ROWS, TARGET_ROWS,
                    DIFFERING_KEY_COUNT, DETAILS, EXPLANATION
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s), %s)""",
                (
                    run,
                    business_date,
                    unit["unit"],
                    unit["status"],
                    unit["source_rows"],
                    unit["target_rows"],
                    unit["differing_key_count"],
                    json.dumps(unit["differences"], default=str),
                    unit.get("explanation", ""),
                ),
            )


def reread(output_dir: Path, run: str, business_date: str) -> int:
    payload = json.loads((output_dir / "ledger.json").read_text(encoding="utf-8"))
    if payload.get("run") != run or payload.get("date") != business_date:
        raise ValueError("ledger.json does not match the requested run and date")
    units = payload.get("units", [])
    explanations = read_explanations(output_dir / "ledger.md")
    for unit in units:
        if unit["status"] == "DIVERGE":
            unit["explanation"] = explanations.get(unit["unit"], "")
    print(summary_line(units))
    return exit_code(units)


def run_gate(run: str, business_date_text: str, manifest_path: Path, output_dir: Path) -> int:
    validate_run(run)
    business_date = date.fromisoformat(business_date_text)
    manifest = load_manifest(manifest_path)
    prefix = object_prefix(run)
    results: list[dict[str, Any]] = []
    source_connection: Any | None = None
    with dbt_connection(run) as target_connection, target_connection.cursor() as target_cursor:
        for unit in manifest:
            schema, relation = relation_parts(unit["target_model"])
            if not target_exists(target_cursor, prefix, schema, relation):
                results.append(
                    {
                        "unit": unit["unit"],
                        "status": "PENDING",
                        "source_rows": 0,
                        "target_rows": 0,
                        "differing_key_count": 0,
                        "differences": [],
                        "explanation": "",
                    }
                )
                continue
            target_columns = relation_columns(target_cursor, prefix, schema, relation)
            compared_columns = [*unit["keys"], *unit["columns"]]
            require_columns(unit["unit"], compared_columns, target_columns, "Snowflake")
            source_schema, source_table = source_parts(unit["owned_table"])
            if source_connection is None:
                source_connection = connect_source_database()
            with source_connection.cursor(as_dict=False) as source_cursor:
                source_cursor.execute(
                    """SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s""",
                    (source_schema, source_table),
                )
                source_columns = {str(row[0]).lower() for row in source_cursor.fetchall()}
            require_columns(unit["unit"], compared_columns, source_columns, "SQL Server")
            source_frame = fetch_source_frame(source_connection, unit, business_date)
            target_frame = fetch_target_frame(
                target_cursor, prefix, schema, relation, unit, business_date
            )
            results.append(
                result_dict(
                    unit["unit"],
                    compare_frames(source_frame, target_frame, unit["keys"], unit["columns"]),
                )
            )
        if source_connection is not None:
            source_connection.close()
        write_ledger(output_dir, run, business_date_text, results)
        record_ledger(target_connection, run, business_date_text, results)
    print(summary_line(results))
    return exit_code(results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--manifest", type=Path, default=HERE / "manifest.yaml")
    parser.add_argument("--out", type=Path, default=HERE / "out")
    parser.add_argument("--reread", action="store_true")
    args = parser.parse_args()
    try:
        if args.reread:
            return reread(args.out, args.run, args.date)
        return run_gate(args.run, args.date, args.manifest, args.out)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
