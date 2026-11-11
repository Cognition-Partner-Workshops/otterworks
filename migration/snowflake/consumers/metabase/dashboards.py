"""Build each Tableau workbook as a Metabase dashboard on SQL Server and on Snowflake.

The legacy workbook in source/tableau/ becomes a dashboard in the "SQL Server" collection,
running its T-SQL custom SQL against OtterWorksUBW. When target/tableau/ holds the migrated
copy, the same dashboard is built in the "Snowflake" collection from that copy's Snowflake
SQL, against the run's database as the read-only viewer. Each worksheet is one card: the
datasource SQL wrapped in the aggregation, sort and mark the worksheet draws, so the two
dashboards differ only in their connection. Reruns update cards and dashboards in place.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gate" / "bi"))
import twb  # noqa: E402

SPEC = ROOT / "gate" / "bi" / "workbooks.yaml"
LEGACY_DIR = ROOT / "source" / "tableau"
TARGET_DIR = ROOT / "target" / "tableau"
GRID_COLUMNS = 24
GRID_ROWS = 36
PARAM = re.compile(r"<\[Parameters\]\.\[([^\]]+)\]>")
AGGREGATES = {"sum": "SUM({})", "cnt": "COUNT({})", "avg": "AVG(CAST({} AS FLOAT))"}
DISPLAY = {"Bar": "row", "Line": "line", "Text": "table"}
# Metabase folds row-chart bars that do not fit the card into "Other", so a bar card is
# grown until every bar Tableau draws has room.
BAR_PIXELS = 32
GRID_ROW_PIXELS = 60
CARD_CHROME_ROWS = 3
NAMESPACE = uuid.UUID("5f0c3a4e-8d1b-4c2e-9a77-0b6f3d2a1e90")


@dataclass
class Side:
    collection: str
    database: str
    engine: str
    details: dict[str, Any]
    heading: str


def tag(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def title(name: str) -> str:
    return " ".join(word.capitalize() for word in name.split("_"))


def stable_id(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


def strip_order(sql: str) -> str:
    """Drop a trailing ORDER BY so the query can be a derived table on both engines."""
    if re.search(r"\bTOP\s*\(|\bLIMIT\s+\d+", sql, re.I):
        return sql
    return re.sub(r"\s+ORDER\s+BY\s+[^()]*$", "", sql.strip(), flags=re.I | re.S)


def measure_alias(agg: str, measure: str) -> str:
    return measure if agg == "sum" else f"{'count' if agg == 'cnt' else 'avg'}_{measure}"


def measure_title(agg: str, measure: str) -> str:
    prefix = {"sum": "", "cnt": "Count of ", "avg": "Average "}[agg]
    return prefix + title(measure)


def card_sql(sheet: twb.Worksheet, datasource_sql: str) -> str:
    """The worksheet's view as SQL: group by its dimensions, aggregate its measures."""
    inner = PARAM.sub(lambda m: "{{" + tag(m.group(1)) + "}}", strip_order(datasource_sql))
    select = [f'{d} AS "{d}"' for d in sheet.dimensions] + [
        f'{AGGREGATES[agg].format(m)} AS "{measure_alias(agg, m)}"' for agg, m in sheet.measures
    ]
    dims = ", ".join(sheet.dimensions)
    positions = [str(i + 1) for i in range(len(sheet.dimensions))]
    by_measure = [f"{len(sheet.dimensions) + 1} DESC"] if sheet.mark == "Bar" else []
    order = by_measure + positions
    return (
        f"SELECT {', '.join(select)}\nFROM (\n{inner}\n) src\n"
        f"GROUP BY {dims}\nORDER BY {', '.join(order)}"
    )


def visualization(sheet: twb.Worksheet) -> dict[str, Any]:
    columns = {d: title(d) for d in sheet.dimensions}
    columns |= {measure_alias(a, m): measure_title(a, m) for a, m in sheet.measures}
    settings: dict[str, Any] = {
        "column_settings": {
            json.dumps(["name", name]): {"column_title": label} for name, label in columns.items()
        }
    }
    if sheet.mark == "Text":
        settings["table.columns"] = [{"name": name, "enabled": True} for name in columns]
    else:
        settings |= {
            "graph.dimensions": list(sheet.dimensions),
            "graph.metrics": [measure_alias(a, m) for a, m in sheet.measures],
            "graph.show_values": True,
            "graph.x_axis.title_text": " / ".join(title(d) for d in sheet.dimensions),
            "graph.y_axis.title_text": " / ".join(measure_title(a, m) for a, m in sheet.measures),
        }
    return settings


def zones(path: Path, dashboard: str) -> dict[str, tuple[int, int, int, int]]:
    """Worksheet name to (col, row, width, height) on Metabase's grid."""
    root = ET.parse(path).getroot()
    board = next(d for d in root.iter("dashboard") if d.get("name") == dashboard)
    placed = {}
    for zone in board.iter("zone"):
        if zone.get("name"):
            x, y, w, h = (int(zone.get(k, "0")) for k in ("x", "y", "w", "h"))
            placed[zone.get("name", "")] = (
                round(x * GRID_COLUMNS / 100000),
                round(y * GRID_ROWS / 100000),
                max(1, round(w * GRID_COLUMNS / 100000)),
                max(2, round(h * GRID_ROWS / 100000)),
            )
    return placed


class Metabase:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")
        self.session = ""

    def call(self, method: str, path: str, body: Any = None) -> Any:
        request = urllib.request.Request(
            self.url + "/api" + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "X-Metabase-Session": self.session},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                text = response.read().decode()
        except urllib.error.HTTPError as error:
            detail = error.read().decode()[:500]
            raise SystemExit(f"{method} {path} failed with {error.code}: {detail}") from None
        return json.loads(text) if text else None

    def login(self, email: str, password: str) -> None:
        properties = self.call("GET", "/session/properties")
        if not properties.get("has-user-setup"):
            self.call(
                "POST",
                "/setup",
                {
                    "token": properties["setup-token"],
                    "user": {
                        "email": email,
                        "password": password,
                        "first_name": "UBW",
                        "last_name": "Admin",
                        "site_name": "OtterWorks UBW",
                    },
                    "prefs": {"site_name": "OtterWorks UBW", "allow_tracking": False},
                },
            )
        self.session = self.call("POST", "/session", {"username": email, "password": password})[
            "id"
        ]

    def database(self, side: Side) -> int:
        existing = self.call("GET", "/database")
        if isinstance(existing, dict):
            existing = existing["data"]
        body = {
            "engine": side.engine,
            "name": side.database,
            "details": side.details,
            "is_full_sync": False,
            "is_on_demand": False,
            "auto_run_queries": True,
        }
        for db in existing:
            if db["name"] == side.database:
                self.call("PUT", f"/database/{db['id']}", body)
                return db["id"]
        return self.call("POST", "/database", body)["id"]

    def collection(self, name: str) -> int:
        for item in self.call("GET", "/collection"):
            top_level = item.get("location") == "/" and not item.get("archived")
            if top_level and item.get("name") == name:
                return item["id"]
        return self.call("POST", "/collection", {"name": name, "parent_id": None})["id"]

    def items(self, collection: int, model: str) -> dict[str, int]:
        found = self.call("GET", f"/collection/{collection}/items?models={model}")
        return {item["name"]: item["id"] for item in found.get("data", found)}

    def row_count(self, card: int) -> int:
        return int(self.call("POST", f"/card/{card}/query", {}).get("row_count", 0))

    def upsert(self, kind: str, collection: int, name: str, body: dict[str, Any]) -> int:
        body = {**body, "name": name, "collection_id": collection}
        existing = self.items(collection, "card" if kind == "card" else "dashboard")
        if name in existing:
            self.call("PUT", f"/{kind}/{existing[name]}", body)
            return existing[name]
        return self.call("POST", f"/{kind}", body)["id"]


def build_dashboard(
    mb: Metabase, side: Side, entry: dict[str, Any], path: Path, business_date: str
) -> int:
    workbook = twb.parse(path)
    board = workbook.dashboards[0] if workbook.dashboards else entry["name"]
    placed = zones(path, board) if workbook.dashboards else {}
    collection = mb.collection(side.collection)
    database = mb.database(side)
    used = [
        name
        for name in workbook.parameters
        if any(f"[Parameters].[{name}]" in ds.sql for ds in workbook.datasources.values())
    ]
    defaults = {**workbook.parameters, "Business Date": business_date}
    parameters, template_tags = [], {}
    for name in used:
        is_date = "date" in name.lower()
        parameters.append(
            {
                "id": stable_id(entry["name"], name),
                "name": name,
                "slug": tag(name),
                "type": "date/single" if is_date else "string/=",
                "sectionId": "date" if is_date else "string",
                "default": defaults[name] if is_date else [defaults[name]],
            }
        )
        template_tags[tag(name)] = {
            "id": stable_id(entry["name"], name, "tag"),
            "name": tag(name),
            "display-name": name,
            "type": "date" if is_date else "text",
            "default": defaults[name],
        }
    dashboard_id = mb.upsert(
        "dashboard",
        collection,
        board,
        {"description": f"{entry['name']} ({entry['file']}), {side.heading}"},
    )
    current = mb.call("GET", f"/dashboard/{dashboard_id}")
    by_card = {dc.get("card_id"): dc["id"] for dc in current.get("dashcards", [])}
    dashcards: list[dict[str, Any]] = [
        {
            "id": by_card.get(None, -1),
            "card_id": None,
            "row": 0,
            "col": 0,
            "size_x": GRID_COLUMNS,
            "size_y": 1,
            "parameter_mappings": [],
            "visualization_settings": {
                "virtual_card": {
                    "name": None,
                    "display": "heading",
                    "visualization_settings": {},
                    "dataset_query": {},
                    "archived": False,
                },
                "text": side.heading,
            },
        }
    ]
    for index, sheet in enumerate(workbook.worksheets):
        datasource = workbook.datasources[sheet.datasource]
        query = card_sql(sheet, datasource.sql)
        sheet_tags = {k: v for k, v in template_tags.items() if "{{" + k + "}}" in query}
        card_id = mb.upsert(
            "card",
            collection,
            f"{entry['name']}: {sheet.name}",
            {
                "display": DISPLAY.get(sheet.mark, "table"),
                "description": f"Worksheet {sheet.name!r}, datasource {datasource.caption!r}",
                "visualization_settings": visualization(sheet),
                "dataset_query": {
                    "type": "native",
                    "database": database,
                    "native": {
                        "query": query,
                        "template-tags": sheet_tags,
                    },
                },
            },
        )
        col, row, width, height = placed.get(sheet.name, (0, index * 12, GRID_COLUMNS, 12))
        if sheet.mark == "Bar":
            bars = mb.row_count(card_id)
            height = max(height, -(-bars * BAR_PIXELS // GRID_ROW_PIXELS) + CARD_CHROME_ROWS)
        dashcards.append(
            {
                "id": by_card.get(card_id, -2 - index),
                "card_id": card_id,
                "row": row + 1,
                "col": col,
                "size_x": width,
                "size_y": height,
                "visualization_settings": {"card.title": sheet.name},
                "parameter_mappings": [
                    {
                        "parameter_id": stable_id(entry["name"], name),
                        "card_id": card_id,
                        "target": ["variable", ["template-tag", tag(name)]],
                    }
                    for name in used
                    if tag(name) in sheet_tags
                ],
            }
        )
    reflow(dashcards)
    mb.call(
        "PUT",
        f"/dashboard/{dashboard_id}",
        {"parameters": parameters, "dashcards": dashcards, "tabs": []},
    )
    return dashboard_id


def reflow(dashcards: list[dict[str, Any]]) -> None:
    """Push cards down below any card that grew into them, keeping Tableau's order."""
    placed: list[dict[str, Any]] = []
    for card in sorted(dashcards, key=lambda c: (c["row"], c["col"])):
        for other in placed:
            beside = card["col"] >= other["col"] + other["size_x"] or (
                other["col"] >= card["col"] + card["size_x"]
            )
            if not beside and card["row"] < other["row"] + other["size_y"]:
                card["row"] = other["row"] + other["size_y"]
        placed.append(card)


def sides(run: str) -> tuple[Side, Side]:
    prefix = "OW_UBW_" + re.sub(r"[^A-Z0-9]", "_", run.upper())
    host = os.environ.get("SNOWFLAKE_HOST") or f"{os.environ.get('SNOWFLAKE_ACCOUNT', '')}"
    account = os.environ.get("SNOWFLAKE_ACCOUNT") or host.removesuffix(".snowflakecomputing.com")
    database = os.environ.get("UBW_SQL_DATABASE", "OtterWorksUBW")
    sqlserver = Side(
        collection="SQL Server",
        database=f"UBW SQL Server ({database})",
        engine="sqlserver",
        details={
            "host": os.environ.get("MB_SQLSERVER_HOST", "ubw-sql"),
            "port": int(os.environ.get("MB_SQLSERVER_PORT", "1433")),
            "db": database,
            "user": os.environ.get("UBW_SQL_USER", "sa"),
            "password": os.environ.get("UBW_SQL_PASSWORD", ""),
            "ssl": False,
            "additional-options": "trustServerCertificate=true",
        },
        heading=f"SQL Server ({database}), T-SQL",
    )
    snowflake = Side(
        collection="Snowflake",
        database=f"UBW Snowflake ({run})",
        engine="snowflake",
        details={
            "account": account,
            "user": f"{prefix}_VIEWER",
            "password": os.environ.get("UBW_VIEWER_PASSWORD", ""),
            "use-password": True,
            "warehouse": f"{prefix}_WH",
            "db": prefix,
            "role": f"{prefix}_READER",
            "schema-filters-type": "inclusion",
            "schema-filters-patterns": "MARTS",
        },
        heading=f"Snowflake ({prefix}), Snowflake SQL",
    )
    return sqlserver, snowflake


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True)
    parser.add_argument("--date", help="default Business Date, default the last contract date")
    parser.add_argument("--workbook", action="append", help="workbook name; repeat, default all")
    args = parser.parse_args()
    spec = yaml.safe_load(SPEC.read_text())
    entries = [e for e in spec["workbooks"] if not args.workbook or e["name"] in args.workbook]
    if not entries or (args.workbook and len(entries) != len(set(args.workbook))):
        print(f"unknown workbook in {args.workbook}", file=sys.stderr)
        return 2
    business_date = args.date or spec["business_dates"][-1]
    for name in ("MB_ADMIN_PASSWORD", "UBW_SQL_PASSWORD"):
        if not os.environ.get(name):
            print(f"{name} is not set", file=sys.stderr)
            return 2
    migrated = [e for e in entries if (TARGET_DIR / e["file"]).exists()]
    if migrated and not os.environ.get("UBW_VIEWER_PASSWORD"):
        print("UBW_VIEWER_PASSWORD is not set", file=sys.stderr)
        return 2
    url = os.environ.get("MB_URL", "http://127.0.0.1:3000")
    mb = Metabase(url)
    email = os.environ.get("MB_ADMIN_EMAIL", "admin@otterworks.local")
    mb.login(email, os.environ["MB_ADMIN_PASSWORD"])
    sqlserver, snowflake = sides(args.run)
    for entry in entries:
        legacy = build_dashboard(mb, sqlserver, entry, LEGACY_DIR / entry["file"], business_date)
        line = f"{entry['name']:<28} SQL Server {url}/dashboard/{legacy}"
        if entry in migrated:
            target_path = TARGET_DIR / entry["file"]
            target = build_dashboard(mb, snowflake, entry, target_path, business_date)
            line += f"  Snowflake {url}/dashboard/{target}"
        else:
            line += "  Snowflake: not migrated"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
