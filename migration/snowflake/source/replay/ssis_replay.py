#!/usr/bin/env python3
"""Interpret the source fixture's SSIS package subset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pymssql

SNOWFLAKE_ROOT = Path(__file__).resolve().parents[2]
SOURCE = SNOWFLAKE_ROOT / "source"
DTS = "www.microsoft.com/SqlServer/Dts"
PIPELINE = "http://schemas.microsoft.com/sqlserver/dts/pipeline"
SQL_TASK = "www.microsoft.com/sqlserver/dts/tasks/sqltask"
SCRIPT_TASK = "www.microsoft.com/sqlserver/dts/tasks/scripttask"
NAMESPACES = {"DTS": DTS, "pipeline": PIPELINE, "SQLTask": SQL_TASK, "ScriptTask": SCRIPT_TASK}
TOKEN_RE = re.compile(
    r"\s*(?:(\(\s*DT_[A-Z0-9_]+(?:\s*,\s*\d+)?\s*\))|"
    r"(@\[[^\]]+\])|"
    r'("(?:[^"]|"")*")|'
    r"(\d+(?:\.\d+)?)|"
    r"(==|!=|&&|\|\||>=|<=|[()+\-*/!,?:<>])|"
    r"([A-Za-z_][A-Za-z0-9_.]*))"
)


@dataclass(frozen=True)
class ConnectionManager:
    name: str
    manager_type: str
    connection_string: str


@dataclass(frozen=True)
class DerivedColumn:
    name: str
    expressions: dict[str, str]


@dataclass(frozen=True)
class Lookup:
    name: str
    join_input: str
    join_reference: str
    outputs: tuple[tuple[str, str], ...]
    reference_file: str | None
    reference_query: str | None


@dataclass(frozen=True)
class Component:
    name: str
    component_type: str
    connection_manager: str | None = None
    derived: DerivedColumn | None = None
    lookup: Lookup | None = None
    destination_table: str | None = None
    mappings: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DataFlow:
    name: str
    source_connection: str
    components: tuple[Component, ...]
    destination_table: str
    mappings: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Executable:
    name: str
    executable_type: str
    sql: str | None = None
    script_intent: str | None = None
    script_arguments: dict[str, str] = field(default_factory=dict)
    script_body: str = ""
    data_flow: DataFlow | None = None


@dataclass(frozen=True)
class Package:
    name: str
    path: Path
    connection_managers: dict[str, ConnectionManager]
    parameters: dict[str, str]
    variables: dict[str, str]
    executables: tuple[Executable, ...]


def _tag(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _property_value(element: ET.Element, property_name: str) -> str | None:
    for child in element:
        if child.tag == _tag(DTS, "Property") and child.get(_tag(DTS, "Name")) == property_name:
            return child.text or ""
    return None


def _component_properties(element: ET.Element) -> dict[str, str]:
    return {
        child.get(_tag(PIPELINE, "name"), ""): child.text or ""
        for child in element
        if child.tag == _tag(PIPELINE, "Property")
    }


def _parse_outputs(value: str) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for item in value.split(";"):
        if not item:
            continue
        output, reference = item.split("=", 1)
        pairs.append((output.strip(), reference.strip()))
    return tuple(pairs)


def _parse_component(element: ET.Element) -> Component:
    component_type = element.get(_tag(PIPELINE, "ComponentType"), "")
    component_name = element.get(_tag(PIPELINE, "Name"), "")
    if component_type == "DerivedColumn":
        expressions = {
            item.get(_tag(PIPELINE, "output"), ""): item.get(_tag(PIPELINE, "expression"), "")
            for item in element.findall("pipeline:Expression", NAMESPACES)
        }
        return Component(
            name=component_name,
            component_type=component_type,
            derived=DerivedColumn(component_name, expressions),
        )
    if component_type == "Lookup":
        properties = _component_properties(element)
        lookup = Lookup(
            name=component_name,
            join_input=properties["JoinInput"],
            join_reference=properties["JoinReference"],
            outputs=_parse_outputs(properties.get("Outputs", "")),
            reference_file=properties.get("ReferenceFile") or None,
            reference_query=properties.get("ReferenceQuery") or None,
        )
        return Component(component_name, component_type, lookup=lookup)
    if component_type == "OLEDBDestination":
        properties = _component_properties(element)
        mappings = tuple(
            (
                item.get(_tag(PIPELINE, "input"), ""),
                item.get(_tag(PIPELINE, "destination"), ""),
            )
            for item in element.findall("pipeline:Mapping", NAMESPACES)
        )
        table = properties.get("TableName", "")
        return Component(
            component_name,
            component_type,
            destination_table=table,
            mappings=mappings,
        )
    return Component(
        name=component_name,
        component_type=component_type,
        connection_manager=element.get(_tag(PIPELINE, "ConnectionManager")),
    )


def _parse_data_flow(element: ET.Element) -> DataFlow:
    pipeline = element.find(".//pipeline:Pipeline", NAMESPACES)
    if pipeline is None:
        raise ValueError(f"Data Flow task {element.get(_tag(DTS, 'ObjectName'))} has no pipeline")
    components = tuple(
        _parse_component(component)
        for component in pipeline.findall(".//pipeline:component", NAMESPACES)
    )
    source = next(
        (
            component
            for component in components
            if component.component_type == "FlatFileSource"
        ),
        None,
    )
    destination = next(
        (
            component
            for component in components
            if component.component_type == "OLEDBDestination"
        ),
        None,
    )
    if source is None or source.connection_manager is None or destination is None:
        raise ValueError("Each Data Flow task needs a flat-file source and OLE DB destination")
    return DataFlow(
        name=element.get(_tag(DTS, "ObjectName"), ""),
        source_connection=source.connection_manager,
        components=components,
        destination_table=destination.destination_table or "",
        mappings=destination.mappings,
    )


def parse_package(path: str | Path) -> Package:
    package_path = Path(path)
    if not package_path.exists():
        candidate = SOURCE / "ssis" / package_path.name
        if candidate.suffix != ".dtsx":
            candidate = candidate.with_suffix(".dtsx")
        package_path = candidate
    root = ET.parse(package_path).getroot()
    if root.get(_tag(DTS, "ExecutableType")) != "Microsoft.Package":
        raise ValueError(f"{package_path} is not an SSIS package")

    connection_managers: dict[str, ConnectionManager] = {}
    for element in root.findall(".//DTS:ConnectionManagers/DTS:ConnectionManager", NAMESPACES):
        name = element.get(_tag(DTS, "ObjectName"), "")
        connection_managers[name] = ConnectionManager(
            name=name,
            manager_type=element.get(_tag(DTS, "CreationName"), ""),
            connection_string=_property_value(element, "ConnectionString") or "",
        )
    parameters = {
        element.get(_tag(DTS, "ObjectName"), ""): _property_value(element, "Value") or ""
        for element in root.findall(".//DTS:PackageParameters/DTS:PackageParameter", NAMESPACES)
    }
    variables = {
        element.get(_tag(DTS, "ObjectName"), ""): _property_value(element, "Value") or ""
        for element in root.findall(".//DTS:Variables/DTS:Variable", NAMESPACES)
    }

    tasks_parent = root.find("DTS:Executables", NAMESPACES)
    executables: list[Executable] = []
    if tasks_parent is not None:
        for element in tasks_parent.findall("DTS:Executable", NAMESPACES):
            name = element.get(_tag(DTS, "ObjectName"), "")
            executable_type = element.get(_tag(DTS, "ExecutableType"), "")
            if executable_type == "Microsoft.Pipeline":
                executables.append(
                    Executable(name, executable_type, data_flow=_parse_data_flow(element))
                )
                continue
            if executable_type == "Microsoft.ExecuteSQLTask":
                sql_element = element.find(".//SQLTask:SqlTaskData", NAMESPACES)
                sql = (
                    sql_element.get(_tag(SQL_TASK, "SqlStatementSource"), "")
                    if sql_element is not None
                    else ""
                )
                executables.append(Executable(name, executable_type, sql=sql))
                continue
            if executable_type == "Microsoft.ScriptTask":
                annotation = "\n".join(
                    item.findtext("DTS:Text", default="", namespaces=NAMESPACES)
                    or item.text
                    or ""
                    for item in element.findall(".//DTS:Annotation", NAMESPACES)
                )
                intent_match = re.search(
                    r"Replay intent:\s*([a-z_]+)\(([^)]*)\)", annotation, re.IGNORECASE
                )
                if intent_match is None:
                    raise ValueError(f"Script Task {name} has no replay intent")
                arguments = {
                    key.strip(): value.strip()
                    for key, value in re.findall(
                        r"([a-z_]+)\s*=\s*([^,\s)]+)", intent_match.group(2)
                    )
                }
                body = "\n".join(
                    item.text or ""
                    for item in element.findall(".//ScriptTask:ScriptMain.cs", NAMESPACES)
                )
                executables.append(
                    Executable(
                        name,
                        executable_type,
                        script_intent=intent_match.group(1),
                        script_arguments=arguments,
                        script_body=body,
                    )
                )
                continue
            executables.append(Executable(name, executable_type))

    return Package(
        name=root.get(_tag(DTS, "ObjectName"), package_path.stem),
        path=package_path,
        connection_managers=connection_managers,
        parameters=parameters,
        variables=variables,
        executables=tuple(executables),
    )


class ExpressionEvaluator:
    def __init__(self, expression: str, row: dict[str, Any], variables: dict[str, Any]):
        self.expression = expression
        self.row = row
        self.variables = variables
        self.tokens = self._tokenize(expression)
        self.index = 0

    @staticmethod
    def _tokenize(expression: str) -> list[str]:
        tokens: list[str] = []
        offset = 0
        while offset < len(expression):
            match = TOKEN_RE.match(expression, offset)
            if match is None:
                if expression[offset:].strip() == "":
                    break
                raise ValueError(f"Unsupported SSIS expression near {expression[offset:]!r}")
            tokens.append(next(group for group in match.groups() if group is not None))
            offset = match.end()
        return tokens

    def _peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self, expected: str | None = None) -> str:
        token = self._peek()
        if token is None or (expected is not None and token != expected):
            raise ValueError(f"Expected {expected or 'an expression token'} in {self.expression!r}")
        self.index += 1
        return token

    def evaluate(self) -> Any:
        result = self._conditional()
        if self._peek() is not None:
            raise ValueError(f"Unexpected token {self._peek()} in {self.expression!r}")
        return result

    def _conditional(self) -> Any:
        condition = self._or()
        if self._peek() == "?":
            self._take("?")
            when_true = self._conditional()
            self._take(":")
            when_false = self._conditional()
            return when_true if bool(condition) else when_false
        return condition

    def _or(self) -> Any:
        value = self._and()
        while self._peek() == "||":
            self._take()
            right = self._and()
            value = bool(value) or bool(right)
        return value

    def _and(self) -> Any:
        value = self._compare()
        while self._peek() == "&&":
            self._take()
            right = self._compare()
            value = bool(value) and bool(right)
        return value

    def _compare(self) -> Any:
        value = self._add()
        while self._peek() in {"==", "!=", ">", "<", ">=", "<="}:
            operator = self._take()
            right = self._add()
            if operator == "==":
                value = value == right
            elif operator == "!=":
                value = value != right
            elif operator == ">":
                value = value > right
            elif operator == "<":
                value = value < right
            elif operator == ">=":
                value = value >= right
            else:
                value = value <= right
        return value

    def _add(self) -> Any:
        value = self._multiply()
        while self._peek() in {"+", "-"}:
            operator = self._take()
            right = self._multiply()
            if operator == "+" and isinstance(value, str) and isinstance(right, str):
                value += right
            else:
                left_number, right_number = self._numbers(value, right)
                value = (
                    left_number + right_number
                    if operator == "+"
                    else left_number - right_number
                )
        return value

    def _multiply(self) -> Any:
        value = self._unary()
        while self._peek() in {"*", "/"}:
            operator = self._take()
            right = self._unary()
            left_number, right_number = self._numbers(value, right)
            if operator == "*":
                value = left_number * right_number
            elif isinstance(left_number, int) and isinstance(right_number, int):
                value = int(left_number / right_number)
            else:
                value = left_number / right_number
        return value

    def _unary(self) -> Any:
        token = self._peek()
        if token in {"!", "-"}:
            operator = self._take()
            value = self._unary()
            return not bool(value) if operator == "!" else -value
        if token is not None and token.startswith("(DT_"):
            data_type = self._take()
            return self._cast(data_type, self._unary())
        return self._primary()

    def _primary(self) -> Any:
        token = self._take()
        if token == "(":
            value = self._conditional()
            self._take(")")
            return value
        if token.startswith('"'):
            return token[1:-1].replace('""', '"')
        if token.startswith("@["):
            key = token[2:-1]
            return self.variables.get(key)
        if token[0].isdigit():
            return float(token) if "." in token else int(token)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", token):
            name = token.upper()
            if name == "NULL" and self._peek() is not None and self._peek().startswith("(DT_"):
                self._take()
                return None
            if self._peek() == "(":
                self._take("(")
                if name == "NULL":
                    self._take()
                    self._take(")")
                    return None
                arguments: list[Any] = []
                if self._peek() != ")":
                    arguments.append(self._conditional())
                    while self._peek() == ",":
                        self._take(",")
                        arguments.append(self._conditional())
                self._take(")")
                return self._call(name, arguments)
            if name in {"TRUE", "FALSE"}:
                return name == "TRUE"
            return self._column(token)
        raise ValueError(f"Unexpected token {token!r} in {self.expression!r}")

    def _column(self, name: str) -> Any:
        if name in self.row:
            return self.row[name]
        lowercase = name.lower()
        for key, value in self.row.items():
            if key.lower() == lowercase:
                return value
        raise KeyError(f"Unknown column {name!r} in SSIS expression")

    @staticmethod
    def _numbers(left: Any, right: Any) -> tuple[int | float, int | float]:
        def convert(value: Any) -> int | float:
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int | float):
                return value
            if isinstance(value, str):
                return float(value) if "." in value else int(value)
            raise TypeError(f"Cannot use {type(value).__name__} as an SSIS number")

        return convert(left), convert(right)

    @staticmethod
    def _cast(data_type: str, value: Any) -> Any:
        normalized = data_type.upper().replace(" ", "")
        if value is None:
            return None
        if normalized.startswith("(DT_I4") or normalized.startswith("(DT_I8"):
            return int(float(value))
        if normalized.startswith("(DT_BOOL"):
            if isinstance(value, bool):
                return value
            return str(value).lower() in {"true", "t", "1"}
        if normalized.startswith("(DT_WSTR"):
            return str(value)
        if normalized.startswith("(DT_DBTIMESTAMP2"):
            if isinstance(value, datetime):
                return value
            if isinstance(value, date):
                return datetime.combine(value, datetime.min.time())
            text = str(value).strip().replace("Z", "")
            if text.endswith("+00"):
                text = text[:-3]
            return datetime.fromisoformat(text)
        return value

    def _call(self, name: str, arguments: list[Any]) -> Any:
        if name == "ISNULL":
            return arguments[0] is None
        if name == "REPLACE":
            return None if arguments[0] is None else str(arguments[0]).replace(
                str(arguments[1]), str(arguments[2])
            )
        if name == "SUBSTRING":
            if arguments[0] is None:
                return None
            start = int(arguments[1]) - 1
            return str(arguments[0])[start : start + int(arguments[2])]
        if name == "FINDSTRING":
            if arguments[0] is None:
                return 0
            text = str(arguments[0])
            needle = str(arguments[1])
            occurrence = int(arguments[2])
            start = 0
            for _ in range(occurrence):
                found = text.find(needle, start)
                if found < 0:
                    return 0
                start = found + len(needle)
            return found + 1
        if name == "LOWER":
            return None if arguments[0] is None else str(arguments[0]).lower()
        if name == "UPPER":
            return None if arguments[0] is None else str(arguments[0]).upper()
        if name == "TRIM":
            return None if arguments[0] is None else str(arguments[0]).strip()
        if name == "ROUND":
            places = int(arguments[1]) if len(arguments) > 1 else 0
            quantum = Decimal(1).scaleb(-places)
            return float(Decimal(str(arguments[0])).quantize(quantum, rounding=ROUND_HALF_UP))
        if name == "DATEADD":
            part, amount, timestamp = arguments
            if not isinstance(timestamp, datetime):
                timestamp = self._cast("(DT_DBTIMESTAMP2,7)", timestamp)
            units = str(part).lower()
            if units in {"ss", "second", "seconds"}:
                return timestamp + timedelta(seconds=int(amount))
            if units in {"mi", "minute", "minutes"}:
                return timestamp + timedelta(minutes=int(amount))
            if units in {"hh", "hour", "hours"}:
                return timestamp + timedelta(hours=int(amount))
            if units in {"dd", "day", "days"}:
                return timestamp + timedelta(days=int(amount))
            raise ValueError(f"Unsupported DATEADD date part {part}")
        if name == "GETDATE":
            return self.variables.get("System::StartTime", datetime.now())
        raise ValueError(f"Unsupported SSIS function {name}")


def evaluate_expression(
    expression: str, row: dict[str, Any], variables: dict[str, Any] | None = None
) -> Any:
    return ExpressionEvaluator(expression, row, variables or {}).evaluate()


def _connect() -> Any:
    return pymssql.connect(
        server=os.environ.get("UBW_SQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("UBW_SQL_PORT", "14333")),
        user=os.environ.get("UBW_SQL_USER", "sa"),
        password=os.environ.get("UBW_SQL_PASSWORD", "OtterUbw_2016dev"),
        database=os.environ.get("UBW_SQL_DATABASE", "OtterWorksUBW"),
        autocommit=True,
    )


def _server_now(connection: Any) -> datetime:
    cursor = connection.cursor()
    cursor.execute("SELECT GETDATE()")
    row = cursor.fetchone()
    cursor.close()
    if row is None:
        raise RuntimeError("SQL Server did not return its local time")
    return row[0]


def _run_start_log(connection: Any, package_name: str, business_date: str) -> int:
    cursor = connection.cursor()
    cursor.execute(
        """
        SET NOCOUNT ON;
        DECLARE @run_id int;
        EXEC dbo.usp_log_run
            @object_name = %s,
            @object_type = 'package',
            @business_date = %s,
            @status = 'started',
            @run_id = @run_id OUTPUT;
        SELECT @run_id;
        """,
        (package_name, business_date),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"usp_log_run did not return a run id for {package_name}")
    run_id = int(row[0])
    cursor.close()
    return run_id


def _run_finish_log(
    connection: Any,
    package_name: str,
    run_id: int,
    status: str,
    rows_read: int,
    rows_written: int,
    message: str | None = None,
) -> None:
    cursor = connection.cursor()
    cursor.execute(
        """
        EXEC dbo.usp_log_run
            @object_name = %s,
            @object_type = 'package',
            @status = %s,
            @rows_read = %s,
            @rows_written = %s,
            @message = %s,
            @run_id = %s;
        """,
        (package_name, status, rows_read, rows_written, message, run_id),
    )
    cursor.close()


def _iter_csv(path: Path) -> Iterator[list[str] | dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        yield headers
        for row in reader:
            yield {key: (value if value != "" else None) for key, value in row.items()}


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    iterator = _iter_csv(path)
    headers = next(iterator)
    return headers, list(iterator)


def _lookup_values(
    connection: Any,
    lookup: Lookup,
    extract_root: Path,
) -> dict[str, dict[str, Any]]:
    if lookup.reference_file:
        headers, rows = _read_csv(extract_root / lookup.reference_file)
        if lookup.join_reference not in headers:
            raise ValueError(
                f"{lookup.reference_file} has no lookup key {lookup.join_reference}"
            )
    elif lookup.reference_query:
        cursor = connection.cursor()
        cursor.execute(lookup.reference_query)
        headers = [column[0] for column in cursor.description or []]
        rows = [dict(zip(headers, values, strict=True)) for values in cursor.fetchall()]
        cursor.close()
    else:
        raise ValueError(f"Lookup {lookup.name} has no reference source")
    return {
        str(row[lookup.join_reference]): row
        for row in rows
        if row.get(lookup.join_reference) is not None
    }


def _staging_columns(table_name: str) -> list[str]:
    schema, table = table_name.replace("[", "").replace("]", "").split(".", 1)
    ddl_path = SOURCE / "ddl" / f"{schema.lower()}.sql"
    sql = ddl_path.read_text(encoding="utf-8")
    match = re.search(
        rf"CREATE TABLE\s+{re.escape(schema)}\.{re.escape(table)}\s*\((.*?)\);",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise ValueError(f"Could not find destination table {table_name} in DDL")
    columns: list[str] = []
    for line in match.group(1).splitlines():
        column_match = re.match(r"\s*(\[?[A-Za-z_]\w*\]?)\s+", line)
        if column_match:
            name = column_match.group(1).strip("[]")
            if name.upper() not in {"CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN"}:
                columns.append(name)
    return columns


def _write_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f") + "0"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return format(value, ".12g")
    return value


def _bulk_load(connection: Any, table_name: str) -> None:
    schema, table = table_name.replace("[", "").replace("]", "").split(".", 1)
    if not re.fullmatch(r"[A-Za-z_]\w*", schema) or not re.fullmatch(r"[A-Za-z_]\w*", table):
        raise ValueError(f"Invalid destination table {table_name}")
    container_path = f"/var/opt/ubw/build/replay/{table}.csv"
    cursor = connection.cursor()
    cursor.execute(
        f"""
        BULK INSERT [{schema}].[{table}]
        FROM '{container_path}'
        WITH (
            FORMAT = 'CSV',
            FIRSTROW = 2,
            KEEPNULLS,
            TABLOCK,
            ROWTERMINATOR = '0x0a'
        )
        """
    )
    cursor.close()


def _timestamp_value(value: Any) -> datetime | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "")
    if text.endswith("+00"):
        text = text[:-3]
    return datetime.fromisoformat(text)


def _run_data_flow(
    connection: Any,
    package: Package,
    data_flow: DataFlow,
    variables: dict[str, Any],
    intents: dict[str, dict[str, str]],
    extract_root: Path,
) -> tuple[int, int]:
    source_manager = package.connection_managers[data_flow.source_connection]
    file_name = source_manager.connection_string.replace("\\", "/").rsplit("/", 1)[-1]
    extract_path = extract_root / file_name
    source_rows = _iter_csv(extract_path)
    headers = next(source_rows)
    if not headers:
        raise ValueError(f"{extract_path} has no CSV header")
    output_columns = _staging_columns(data_flow.destination_table)
    mappings = (
        {destination: input_column for input_column, destination in data_flow.mappings}
        or {column: column for column in output_columns}
    )
    lookup_caches = {
        component.name: _lookup_values(connection, component.lookup, extract_root)
        for component in data_flow.components
        if component.lookup is not None
    }
    destination_table = data_flow.destination_table.replace("[", "").replace("]", "")
    destination_path = SOURCE / "build" / "replay" / f"{destination_table.split('.')[-1]}.csv"
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    watermark_value: datetime | None = None
    if "watermark_read" in intents:
        raw_watermark = intents["watermark_read"].get("watermark")
        watermark_value = _timestamp_value(raw_watermark)
    rows_read = 0
    rows_written = 0
    with destination_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(output_columns)
        for row in source_rows:
            rows_read += 1
            if watermark_value is not None and package.name == "pkg_billing_usage":
                source_time = _timestamp_value(row.get("occurred_at"))
                if source_time is None or source_time <= watermark_value:
                    continue
            for component in data_flow.components:
                if component.derived is not None:
                    for output, expression in component.derived.expressions.items():
                        row[output] = evaluate_expression(expression, row, variables)
                elif component.lookup is not None:
                    lookup = component.lookup
                    lookup_key = row.get(lookup.join_input)
                    match = (
                        lookup_caches[component.name].get(str(lookup_key))
                        if lookup_key is not None
                        else None
                    )
                    for output, reference_column in lookup.outputs:
                        row[output] = match.get(reference_column) if match else None
            if "unit_conversion" in intents:
                size_bytes = row.get("size_bytes")
                row["size_mb"] = (
                    round(int(size_bytes) / 1_048_576.0, 3) if size_bytes is not None else None
                )
            if "checksum" in intents:
                checksum_fields = (
                    "event_id",
                    "event_type",
                    "user_id",
                    "resource_id",
                    "occurred_at",
                )
                payload = "|".join(str(row.get(field, "")) for field in checksum_fields)
                row["row_checksum"] = hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()
            writer.writerow([_write_value(row.get(mappings[column])) for column in output_columns])
            rows_written += 1
    if rows_written:
        _bulk_load(connection, data_flow.destination_table)
    return rows_read, rows_written


def _dispatch_script(
    connection: Any, executable: Executable, intents: dict[str, dict[str, str]]
) -> None:
    if executable.script_intent is None:
        raise ValueError(f"Script Task {executable.name} has no replay intent")
    intent = executable.script_intent
    arguments = executable.script_arguments
    if intent == "watermark_read":
        cursor = connection.cursor()
        cursor.execute(
            "SELECT watermark_value FROM ops.parity_watermarks WHERE object_name = %s",
            (arguments.get("object_name", "pkg_billing_usage"),),
        )
        row = cursor.fetchone()
        cursor.close()
        intents[intent] = {"watermark": row[0] if row else ""}
        return
    if intent in {"unit_conversion", "checksum"}:
        intents[intent] = arguments
        return
    raise ValueError(f"Unsupported Script Task intent {intent}")


def _sql_with_variables(sql: str, variables: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = f"{match.group(1)}::{match.group(2)}"
        value = variables.get(key)
        if value is None:
            return "NULL"
        if isinstance(value, datetime | date):
            value = value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    return re.sub(r"@\[(User|System|\$Package)::([A-Za-z0-9_]+)\]", replace, sql)


def run_package(
    package_name: str | Path,
    connection: Any | None = None,
    business_date: date | str | None = None,
    extract_root: str | Path | None = None,
) -> tuple[int, int]:
    package = parse_package(package_name)
    owns_connection = connection is None
    sql_connection = connection or _connect()
    business_date_value = str(
        business_date
        or package.parameters.get("BusinessDate")
        or date(2026, 9, 30).isoformat()
    )
    extracted_at = _server_now(sql_connection)
    variables: dict[str, Any] = {
        "System::StartTime": extracted_at,
        "$Package::BusinessDate": business_date_value,
        "Package::BusinessDate": business_date_value,
    }
    root = Path(extract_root) if extract_root else SOURCE / "build" / "extracts"
    rows_read = 0
    rows_written = 0
    run_id = _run_start_log(sql_connection, package.name, business_date_value)
    intents: dict[str, dict[str, str]] = {}
    try:
        for executable in package.executables:
            if executable.executable_type == "Microsoft.ScriptTask":
                _dispatch_script(sql_connection, executable, intents)
            elif executable.executable_type == "Microsoft.ExecuteSQLTask":
                if executable.sql:
                    cursor = sql_connection.cursor()
                    cursor.execute(_sql_with_variables(executable.sql, variables))
                    cursor.close()
            elif executable.data_flow is not None:
                read_count, written_count = _run_data_flow(
                    sql_connection,
                    package,
                    executable.data_flow,
                    variables,
                    intents,
                    root,
                )
                rows_read += read_count
                rows_written += written_count
        _run_finish_log(
            sql_connection,
            package.name,
            run_id,
            "succeeded",
            rows_read,
            rows_written,
        )
    except Exception as error:
        with suppress(Exception):
            _run_finish_log(
                sql_connection,
                package.name,
                run_id,
                "failed",
                rows_read,
                rows_written,
                str(error)[:4000],
            )
        raise
    finally:
        if owns_connection:
            sql_connection.close()
    return rows_read, rows_written


def _package_path(value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path
    filename = path.name if path.suffix == ".dtsx" else f"{path.name}.dtsx"
    return SOURCE / "ssis" / filename


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay one or more SQL Server SSIS packages.")
    parser.add_argument("package", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--business-date", type=date.fromisoformat)
    parser.add_argument("--extract-root", type=Path)
    args = parser.parse_args(argv)
    if not args.all and not args.package:
        parser.error("provide a package name or --all")
    paths = (
        sorted((SOURCE / "ssis").glob("*.dtsx"))
        if args.all
        else [_package_path(args.package)]
    )
    connection = _connect()
    try:
        for path in paths:
            counts = run_package(
                path,
                connection,
                args.business_date,
                args.extract_root,
            )
            print(f"{path.stem}: rows_read={counts[0]} rows_written={counts[1]}")
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
