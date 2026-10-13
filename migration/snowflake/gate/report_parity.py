"""Compare every SSRS report dataset on SQL Server with its REPORTS view in Snowflake.

For each `source/reports/<report>.rdl` the SQL Server side runs the report's own DataSet query
with its parameters (@BusinessDate and the report's default for any other parameter); the
Snowflake side selects the same fields from `REPORTS.<report>` filtered on the same values. Rows
are matched on the keys in `reports.yaml`, or compared as multisets of whole rows when a report
has no natural key. The result goes to gate/out/reports.json and reports.md and is appended to
OPS.REPORT_PARITY_LEDGER. Explanations are written by hand under each diverging report in
reports.md and carry forward while it still diverges, as in the unit ledger.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
REPORTS_DIR = HERE.parent / "source" / "reports"
sys.path[:0] = [str(HERE), str(HERE.parent / "target" / "python")]
parity = importlib.import_module("parity")
comparison = importlib.import_module("compare")

RDL_NS = {"r": "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"}
PARAMETER = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass
class ReportDefinition:
    name: str
    command_text: str
    fields: list[str]
    defaults: dict[str, str]
    keys: list[str] | None = None
    exclude: dict[str, str] = field(default_factory=dict)
    filters: dict[str, str] = field(default_factory=dict)

    @property
    def compared(self) -> list[str]:
        return [name for name in self.fields if name not in self.exclude]


def parse_rdl(path: Path) -> tuple[str, list[str], dict[str, str]]:
    root = ET.parse(path).getroot()  # noqa: S314 - repository-owned report definitions
    command = root.find(".//r:DataSet/r:Query/r:CommandText", RDL_NS)
    if command is None or not (command.text or "").strip():
        raise ValueError(f"{path.name}: no DataSet CommandText")
    fields = [
        element.text or ""
        for element in root.findall(".//r:DataSet/r:Fields/r:Field/r:DataField", RDL_NS)
    ]
    defaults: dict[str, str] = {}
    for parameter in root.findall(".//r:ReportParameters/r:ReportParameter", RDL_NS):
        value = parameter.find("r:DefaultValue/r:Values/r:Value", RDL_NS)
        if value is not None and value.text is not None:
            defaults[parameter.attrib["Name"]] = value.text
    return command.text.strip(), fields, defaults


def load_definitions(manifest_path: Path, reports_dir: Path) -> list[ReportDefinition]:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))["reports"]
    files = sorted(path.stem for path in reports_dir.glob("rpt_*.rdl"))
    if sorted(manifest) != files:
        missing = sorted(set(files) - set(manifest))
        extra = sorted(set(manifest) - set(files))
        raise ValueError(
            f"reports.yaml does not match source/reports: missing {missing}, extra {extra}"
        )
    definitions = []
    for name in files:
        command, fields, defaults = parse_rdl(reports_dir / f"{name}.rdl")
        entry = manifest[name] or {}
        definition = ReportDefinition(
            name=name,
            command_text=command,
            fields=fields,
            defaults=defaults,
            keys=entry.get("keys"),
            exclude=entry.get("exclude") or {},
            filters=entry.get("filters") or {},
        )
        for column in [*(definition.keys or []), *definition.exclude, *definition.filters.values()]:
            if column not in fields:
                raise ValueError(f"{name}: {column!r} is not a field of the report")
        for parameter in PARAMETER.findall(command):
            if parameter != "BusinessDate" and parameter not in definition.filters:
                raise ValueError(f"{name}: parameter @{parameter} has no view column in filters")
        definitions.append(definition)
    return definitions


def parameter_values(definition: ReportDefinition, business_date: date) -> dict[str, Any]:
    values: dict[str, Any] = dict(definition.defaults)
    values["BusinessDate"] = business_date
    return values


def sqlserver_query(definition: ReportDefinition, values: dict[str, Any]) -> tuple[str, tuple]:
    order = PARAMETER.findall(definition.command_text)
    query = PARAMETER.sub("%s", definition.command_text.replace("%", "%%"))
    return query, tuple(values[name] for name in order)


def snowflake_query(
    definition: ReportDefinition, database: str, values: dict[str, Any]
) -> tuple[str, tuple]:
    for name in [definition.name, *definition.fields, *definition.filters.values()]:
        if not IDENTIFIER.fullmatch(name):
            raise ValueError(f"invalid identifier {name!r}")
    select_list = ", ".join(f'"{name.upper()}"' for name in definition.fields)
    query = (
        f'SELECT {select_list} FROM "{database}"."REPORTS"."{definition.name.upper()}" '
        'WHERE "BUSINESS_DATE" = %s'
    )
    parameters: list[Any] = [values["BusinessDate"]]
    for parameter, column in definition.filters.items():
        query += f' AND "{column.upper()}" = %s'
        parameters.append(values[parameter])
    return query, tuple(parameters)


def _normal(value: Any) -> Any:
    value = comparison._as_scalar(value)
    if comparison._is_null(value):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value)).normalize()
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime) and value.utcoffset() is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value


def compare_multiset(
    source: pd.DataFrame, target: pd.DataFrame, columns: list[str]
) -> comparison.UnitResult:
    def rows(frame: pd.DataFrame) -> Counter:
        names = {str(column).lower(): column for column in frame.columns}
        ordered = [names[column.lower()] for column in columns]
        return Counter(
            tuple(_normal(value) for value in row)
            for row in frame[ordered].itertuples(index=False, name=None)
        )

    source_rows, target_rows = rows(source), rows(target)
    differences = []
    for row in sorted(set(source_rows) | set(target_rows), key=str):
        if source_rows[row] != target_rows[row]:
            differences.append(
                {
                    "key": dict(zip(columns, (comparison._display(v) for v in row), strict=True)),
                    "column": "<row count>",
                    "sqlserver": f"{source_rows[row]} rows",
                    "snowflake": f"{target_rows[row]} rows",
                }
            )
    return comparison.UnitResult(
        status="DIVERGE" if differences else "PASS",
        source_rows=len(source),
        target_rows=len(target),
        differing_key_count=len(differences),
        differences=differences[:10],
    )


def compare_report(
    definition: ReportDefinition, source: pd.DataFrame, target: pd.DataFrame
) -> comparison.UnitResult:
    if definition.keys is None:
        return compare_multiset(source, target, definition.compared)
    columns = [name for name in definition.compared if name not in definition.keys]
    return comparison.compare_frames(source, target, definition.keys, columns)


def summary_line(results: list[dict[str, Any]]) -> str:
    counts = Counter(result["status"] for result in results)
    return (
        f"Report parity PASS={counts['PASS']} DIVERGE={counts['DIVERGE']} "
        f"PENDING={counts['PENDING']}"
    )


def write_ledger(output_dir: Path, run: str, business_date: str, results: list[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "reports.md"
    previous = parity.read_explanations(markdown_path)
    for result in results:
        result["explanation"] = (
            previous.get(result["unit"], "") if result["status"] == "DIVERGE" else ""
        )
    payload = {
        "run": run,
        "date": business_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "reports": results,
    }
    (output_dir / "reports.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    lines = [
        summary_line(results),
        "",
        "| Report | Status | Rows (SQL Server / Snowflake) | Differing keys | Parameters |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for result in results:
        lines.append(
            f"| {result['unit']} | {result['status']} | {result['source_rows']} / "
            f"{result['target_rows']} | {result['differing_key_count']} | "
            f"{result['parameters']} |"
        )
    for result in results:
        if result["status"] != "DIVERGE":
            continue
        lines.extend(["", f"### {result['unit']}", ""])
        for difference in result["differences"]:
            lines.append(
                f"- `{json.dumps(difference['key'], sort_keys=True)}` "
                f"`{difference['column']}`: SQL Server `{difference['sqlserver']}`, "
                f"Snowflake `{difference['snowflake']}`"
            )
        lines.append(f"Explanation: {result.get('explanation', '')}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def record_ledger(connection: Any, run: str, business_date: str, results: list[dict]) -> None:
    prefix = parity.object_prefix(run)
    with connection.cursor() as cursor:
        cursor.execute(  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            f"""CREATE TABLE IF NOT EXISTS {prefix}.OPS.REPORT_PARITY_LEDGER (
                RUN_TOKEN VARCHAR,
                BUSINESS_DATE DATE,
                REPORT VARCHAR,
                STATUS VARCHAR,
                SOURCE_ROWS NUMBER,
                TARGET_ROWS NUMBER,
                DIFFERING_KEY_COUNT NUMBER,
                PARAMETERS VARCHAR,
                DETAILS VARIANT,
                EXPLANATION VARCHAR,
                GENERATED_AT TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
            )"""
        )
        for result in results:
            cursor.execute(  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
                f"""INSERT INTO {prefix}.OPS.REPORT_PARITY_LEDGER (
                    RUN_TOKEN, BUSINESS_DATE, REPORT, STATUS, SOURCE_ROWS, TARGET_ROWS,
                    DIFFERING_KEY_COUNT, PARAMETERS, DETAILS, EXPLANATION
                ) SELECT %s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s), %s""",
                (
                    run,
                    business_date,
                    result["unit"],
                    result["status"],
                    result["source_rows"],
                    result["target_rows"],
                    result["differing_key_count"],
                    result["parameters"],
                    json.dumps(result["differences"], default=str),
                    result.get("explanation", ""),
                ),
            )


def exit_code(results: list[dict[str, Any]]) -> int:
    return parity.exit_code(results)


def run_reports(run: str, business_date_text: str, manifest: Path, output_dir: Path) -> int:
    parity.validate_run(run)
    business_date = date.fromisoformat(business_date_text)
    database = parity.object_prefix(run)
    definitions = load_definitions(manifest, REPORTS_DIR)
    results: list[dict[str, Any]] = []
    source_connection = parity.connect_source_database()
    with parity.dbt_connection(run) as target_connection, target_connection.cursor() as cursor:
        for definition in definitions:
            values = parameter_values(definition, business_date)
            shown = ", ".join(
                f"@{name}={values[name]}"
                for name in dict.fromkeys(PARAMETER.findall(definition.command_text))
            )
            if not parity.target_exists(cursor, database, "REPORTS", definition.name.upper()):
                results.append(
                    {
                        "unit": definition.name,
                        "status": "PENDING",
                        "source_rows": 0,
                        "target_rows": 0,
                        "differing_key_count": 0,
                        "differences": [],
                        "parameters": shown,
                    }
                )
                continue
            query, parameters = sqlserver_query(definition, values)
            with source_connection.cursor(as_dict=False) as source_cursor:
                source_cursor.execute(
                    query, parameters
                )  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
                source = pd.DataFrame(
                    source_cursor.fetchall(),
                    columns=[column[0] for column in source_cursor.description],
                )
            query, parameters = snowflake_query(definition, database, values)
            cursor.execute(
                query, parameters
            )  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            target = pd.DataFrame(
                cursor.fetchall(), columns=[column[0] for column in cursor.description]
            )
            result = compare_report(definition, source, target)
            results.append(
                {
                    "unit": definition.name,
                    "status": result.status,
                    "source_rows": result.source_rows,
                    "target_rows": result.target_rows,
                    "differing_key_count": result.differing_key_count,
                    "differences": result.differences,
                    "parameters": shown,
                }
            )
        source_connection.close()
        write_ledger(output_dir, run, business_date_text, results)
        record_ledger(target_connection, run, business_date_text, results)
    print(summary_line(results))
    return exit_code(results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--manifest", type=Path, default=HERE / "reports.yaml")
    parser.add_argument("--out", type=Path, default=HERE / "out")
    args = parser.parse_args()
    try:
        return run_reports(args.run, args.date, args.manifest, args.out)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
