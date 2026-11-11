"""Read the parts of a Tableau .twb that the report parity check needs."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

FIELD = re.compile(r"\[(?P<ds>[^\]]+)\]\.\[(?P<agg>[a-z]+):(?P<field>[^:\]]+):[a-z]+\]")


@dataclass
class Datasource:
    name: str
    caption: str
    connection_class: str
    connection: dict[str, str]
    sql: str
    columns: dict[str, str]


@dataclass
class Worksheet:
    name: str
    datasource: str
    mark: str
    dimensions: list[str] = field(default_factory=list)
    measures: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Workbook:
    path: Path
    parameters: dict[str, str]
    datasources: dict[str, Datasource]
    worksheets: list[Worksheet]
    dashboards: list[str]

    def by_caption(self, caption: str) -> Datasource | None:
        return next((ds for ds in self.datasources.values() if ds.caption == caption), None)


def _fields(shelf: str | None) -> list[tuple[str, str]]:
    return [(match["agg"], match["field"]) for match in FIELD.finditer(shelf or "")]


def _connection(datasource: ET.Element) -> ET.Element | None:
    for connection in datasource.iter("connection"):
        if connection.get("class") != "federated":
            return connection
    return None


def _relation_sql(datasource: ET.Element) -> str:
    for relation in datasource.iter("relation"):
        if relation.get("type") == "text":
            return (relation.text or "").strip()
    return ""


def parse(path: Path) -> Workbook:
    root = ET.parse(path).getroot()
    parameters: dict[str, str] = {}
    datasources: dict[str, Datasource] = {}
    for element in root.find("datasources") or []:
        if element.get("name") == "Parameters":
            for column in element.findall("column"):
                parameters[column.get("name", "").strip("[]")] = column.get("value", "").strip('#"')
            continue
        connection = _connection(element)
        datasources[element.get("name", "")] = Datasource(
            name=element.get("name", ""),
            caption=element.get("caption", element.get("name", "")),
            connection_class=connection.get("class", "") if connection is not None else "",
            connection=dict(connection.attrib) if connection is not None else {},
            sql=_relation_sql(element),
            columns={
                c.get("name", "").strip("[]"): c.get("datatype", "")
                for c in element.findall("column")
            },
        )
    worksheets = []
    for sheet in root.iter("worksheet"):
        view_ds = sheet.find("table/view/datasources/datasource")
        mark = sheet.find("table/panes/pane/mark")
        rows = sheet.findtext("table/rows")
        cols = sheet.findtext("table/cols")
        shelves = _fields(rows) + _fields(cols)
        worksheets.append(
            Worksheet(
                name=sheet.get("name", ""),
                datasource=view_ds.get("name", "") if view_ds is not None else "",
                mark=mark.get("class", "") if mark is not None else "",
                dimensions=[name for agg, name in shelves if agg == "none"],
                measures=[(agg, name) for agg, name in shelves if agg != "none"]
                + _measure_names(sheet),
            )
        )
    dashboards = [d.get("name", "") for d in root.iter("dashboard")]
    return Workbook(path, parameters, datasources, worksheets, dashboards)


def _measure_names(sheet: ET.Element) -> list[tuple[str, str]]:
    found = []
    for member in sheet.iter("groupfilter"):
        if member.get("level") == "[:Measure Names]":
            found.extend(_fields(member.get("member", "").strip('"')))
    return found


def bind(sql: str, parameters: dict[str, str]) -> str:
    """Substitute <[Parameters].[Name]> the way Tableau does, as quoted literals."""

    def literal(match: re.Match[str]) -> str:
        value = parameters[match.group(1)]
        return "'" + value.replace("'", "''") + "'"

    return re.sub(r"<\[Parameters\]\.\[([^\]]+)\]>", literal, sql)
