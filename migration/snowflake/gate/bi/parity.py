"""Report-level parity: run every Tableau datasource on SQL Server and on Snowflake.

The legacy workbook in source/tableau/ runs against SQL Server. Its migrated
copy in target/tableau/ must point at Snowflake. For each datasource both
queries run for the same business date, rows are aligned on the keys in
gate/bi/workbooks.yaml, and every worksheet is aggregated the way Tableau
draws it, so a differing cell shows up on the chart it would change.
Results land in gate/out/bi/ and render.py turns them into the console.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import pickle
import re
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
GATE = HERE.parent
ROOT = GATE.parent
sys.path[:0] = [str(HERE), str(GATE), str(ROOT / "target" / "python")]
twb = importlib.import_module("twb")
comparison = importlib.import_module("compare")

SPEC = HERE / "workbooks.yaml"
LEGACY_DIR = ROOT / "source" / "tableau"
TARGET_DIR = ROOT / "target" / "tableau"
OUT = GATE / "out" / "bi"
LEDGER = GATE / "out" / "ledger.md"
MAX_DIFFS = 200
VIEW_ROWS = {"Bar": 15, "Line": 60, "Text": 25}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_spec() -> dict[str, Any]:
    return yaml.safe_load(SPEC.read_text())


def ledger_status() -> dict[str, str]:
    if not LEDGER.exists():
        return {}
    found = {}
    for line in LEDGER.read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1] in {"PASS", "DIVERGE", "PENDING"}:
            found[cells[0]] = cells[1]
    return found


def scalar(value: Any) -> Any:
    value = comparison._as_scalar(value)
    if comparison._is_null(value):
        return None
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def cells_equal(left: Any, right: Any, tolerance: float) -> bool:
    if comparison._equal(left, right):
        return True
    left, right = scalar(left), scalar(right)
    if (
        isinstance(left, (int, float))
        and isinstance(right, (int, float))
        and not isinstance(left, bool)
    ):
        return abs(left - right) <= max(tolerance, 1e-9 * max(abs(left), abs(right)))
    return left == right


def compare_datasource(
    legacy: pd.DataFrame, target: pd.DataFrame, keys: list[str], tolerance: dict[str, float]
) -> dict[str, Any]:
    legacy = legacy.rename(columns=str.lower)
    target = target.rename(columns=str.lower)
    columns = [c for c in legacy.columns if c not in keys]
    missing = [c for c in [*keys, *columns] if c not in target.columns]
    if missing:
        return {
            "status": "DIVERGE",
            "message": f"Snowflake query has no column {missing[0]!r}",
            "differing_keys": len(legacy),
            "diffs": [],
        }

    def index(frame: pd.DataFrame) -> dict[tuple, list[dict[str, Any]]]:
        rows: dict[tuple, list[dict[str, Any]]] = {}
        for record in frame.to_dict("records"):
            rows.setdefault(tuple(scalar(record[k]) for k in keys), []).append(record)
        return rows

    left, right = index(legacy), index(target)
    diffs, differing = [], 0
    for key in sorted(set(left) | set(right), key=lambda k: tuple(str(v) for v in k)):
        label = dict(zip(keys, key, strict=True))
        a, b = left.get(key, []), right.get(key, [])
        if len(a) != 1 or len(b) != 1:
            differing += 1
            what = (
                "row missing in Snowflake"
                if not b
                else "row missing in SQL Server"
                if not a
                else "duplicate key"
            )
            diffs.append(
                {
                    "key": label,
                    "column": what,
                    "sqlserver": f"{len(a)} rows",
                    "snowflake": f"{len(b)} rows",
                }
            )
            continue
        row_diffs = [
            {"key": label, "column": c, "sqlserver": scalar(a[0][c]), "snowflake": scalar(b[0][c])}
            for c in columns
            if not cells_equal(a[0][c], b[0][c], tolerance.get(c, 0.0))
        ]
        if row_diffs:
            differing += 1
            diffs.extend(row_diffs)
    return {
        "status": "DIVERGE" if differing else "PASS",
        "message": "",
        "differing_keys": differing,
        "diffs": diffs[:MAX_DIFFS],
        "diff_cells": len(diffs),
    }


def view(frame: pd.DataFrame | None, sheet: Any) -> dict[str, dict[str, Any]]:
    if frame is None:
        return {}
    frame = frame.rename(columns=str.lower)
    if any(d not in frame.columns for d in sheet.dimensions) or any(
        m not in frame.columns for _, m in sheet.measures
    ):
        return {}
    data = frame.copy()
    for agg, measure in sheet.measures:
        if agg != "cnt":
            data[measure] = pd.to_numeric(data[measure].map(scalar), errors="coerce")
    for dim in sheet.dimensions:
        data[dim] = data[dim].map(lambda v: "Null" if scalar(v) is None else str(scalar(v)))
    grouped = data.groupby(sheet.dimensions, dropna=False)
    result: dict[str, dict[str, Any]] = {}
    for key, group in grouped:
        label = " · ".join(key) if isinstance(key, tuple) else str(key)
        values = {}
        for agg, measure in sheet.measures:
            series = group[measure]
            value = (
                series.count() if agg == "cnt" else series.mean() if agg == "avg" else series.sum()
            )
            values[f"{agg}:{measure}"] = float(value)
        result[label] = values
    return result


def compare_view(
    sheet: Any, legacy: pd.DataFrame | None, target: pd.DataFrame | None
) -> dict[str, Any]:
    left, right = view(legacy, sheet), view(target, sheet)
    measures = [f"{a}:{m}" for a, m in sheet.measures]
    labels = list(dict.fromkeys([*left, *right]))
    first = measures[0]
    if sheet.mark == "Bar":
        labels.sort(key=lambda label: -(left.get(label) or right.get(label) or {}).get(first, 0))
    else:
        labels.sort()
    rows, differing = [], 0
    for label in labels:
        a, b = left.get(label), right.get(label)
        diff = [
            m
            for m in measures
            if target is not None and (a is None or b is None or not cells_equal(a[m], b[m], 0.0))
        ]
        differing += bool(diff)
        rows.append({"label": label, "legacy": a, "target": b, "diff": diff})
    shown = rows[: VIEW_ROWS.get(sheet.mark, 25)]
    shown += [row for row in rows[len(shown) :] if row["diff"]][:10]
    return {
        "name": sheet.name,
        "mark": sheet.mark,
        "dimensions": sheet.dimensions,
        "measures": measures,
        "marks": len(rows),
        "differing_marks": differing,
        "rows": shown,
    }


def sqlserver_connection() -> Any:
    import pymssql

    return pymssql.connect(
        server=os.environ.get("UBW_SQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("UBW_SQL_PORT", "14333")),
        user=os.environ.get("UBW_SQL_USER", "sa"),
        password=os.environ["UBW_SQL_PASSWORD"],
        database=os.environ.get("UBW_SQL_DATABASE", "OtterWorksUBW"),
        login_timeout=5,
    )


def fetch(connection: Any, sql: str) -> pd.DataFrame:
    cursor = connection.cursor()
    cursor.execute(sql)
    names = [d[0].lower() for d in cursor.description]
    return pd.DataFrame(cursor.fetchall(), columns=names)


def run_workbook(
    entry: dict[str, Any],
    business_date: str,
    run: str,
    source: Any,
    target: Any,
    ledger: dict[str, str],
) -> dict[str, Any]:
    legacy_wb = twb.parse(LEGACY_DIR / entry["file"])
    target_path = TARGET_DIR / entry["file"]
    target_wb = twb.parse(target_path) if target_path.exists() else None
    params = {**legacy_wb.parameters, "Business Date": business_date}
    cache = OUT / "cache" / business_date / slug(entry["name"])
    cache.mkdir(parents=True, exist_ok=True)
    status = "NOT MIGRATED"
    if target_wb is not None:
        classes = {ds.connection_class for ds in target_wb.datasources.values()}
        status = "PASS" if classes == {"snowflake"} else "NOT REPOINTED"
    frames: dict[str, tuple[pd.DataFrame | None, pd.DataFrame | None]] = {}
    datasources = []
    for spec in entry["datasources"]:
        caption = spec["caption"]
        legacy_ds = legacy_wb.by_caption(caption)
        legacy_sql = twb.bind(legacy_ds.sql, params)
        cached = cache / (slug(caption) + ".pkl")
        if source is not None:
            legacy_frame = fetch(source, legacy_sql)
            cached.write_bytes(pickle.dumps(legacy_frame))
        elif cached.exists():
            legacy_frame = pickle.loads(cached.read_bytes())
        else:
            legacy_frame = None
        item: dict[str, Any] = {
            "caption": caption,
            "report": spec["report"],
            "keys": spec["keys"],
            "legacy_sql": legacy_ds.sql,
            "legacy_rows": None if legacy_frame is None else len(legacy_frame),
            "target_sql": None,
            "target_rows": None,
            "connection": None,
            "status": status,
            "message": "",
            "diffs": [],
        }
        target_frame = None
        target_ds = target_wb.by_caption(caption) if target_wb else None
        if target_wb is not None and target_ds is None:
            item.update(status="PENDING", message="datasource missing from the migrated workbook")
        elif target_ds is not None:
            item["target_sql"] = target_ds.sql
            item["connection"] = {
                k: v
                for k, v in target_ds.connection.items()
                if k in {"class", "server", "dbname", "schema", "warehouse", "service"}
            }
            if target_ds.connection_class != "snowflake":
                item.update(
                    status="NOT REPOINTED",
                    message=f"still connects with class {target_ds.connection_class!r}",
                )
            elif target is None:
                item.update(status="PENDING", message="no Snowflake connection")
            else:
                try:
                    target_frame = fetch(target, twb.bind(target_ds.sql, params))
                except (
                    Exception
                ) as error:  # surfaced in the console, e.g. a model that is not built yet
                    item.update(status="PENDING", message=str(error).splitlines()[0][:300])
                if target_frame is not None:
                    item["target_rows"] = len(target_frame)
                if target_frame is not None and legacy_frame is None:
                    item.update(
                        status="PENDING",
                        message="no SQL Server result for this date: "
                        "SQL Server is unreachable and nothing is cached",
                    )
                elif target_frame is not None:
                    item.update(
                        compare_datasource(
                            legacy_frame, target_frame, spec["keys"], spec.get("tolerance", {})
                        )
                    )
        frames[caption] = (legacy_frame, target_frame)
        datasources.append(item)
    order = ["PENDING", "NOT REPOINTED", "DIVERGE", "PASS"]
    if target_wb is not None and status != "NOT REPOINTED":
        status = min((ds["status"] for ds in datasources), key=order.index)
    sheets = []
    for sheet in legacy_wb.worksheets:
        caption = legacy_wb.datasources[sheet.datasource].caption
        legacy_frame, target_frame = frames[caption]
        sheets.append({**compare_view(sheet, legacy_frame, target_frame), "datasource": caption})
    return {
        "workbook": entry["name"],
        "file": entry["file"],
        "folder": entry["folder"],
        "date": business_date,
        "run": run,
        "status": status,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "legacy_tables": entry["legacy_tables"],
        "units": [{"unit": unit, "status": ledger.get(unit, "PENDING")} for unit in entry["units"]],
        "datasources": datasources,
        "sheets": sheets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument(
        "--workbook", action="append", help="workbook name; repeat for more, default all"
    )
    args = parser.parse_args()
    spec = load_spec()
    entries = [e for e in spec["workbooks"] if not args.workbook or e["name"] in args.workbook]
    if not entries:
        print(f"no workbook named {args.workbook}", file=sys.stderr)
        return 2
    try:
        source = sqlserver_connection()
    except Exception as error:
        print(
            f"SQL Server unreachable ({str(error).splitlines()[0][:120]}); "
            "using the last legacy results",
            file=sys.stderr,
        )
        source = None
    target = None
    if any((TARGET_DIR / e["file"]).exists() for e in entries):
        snowflake = importlib.import_module("ubw_snowflake")
        target = snowflake.dbt_connection(args.run)
    ledger = ledger_status()
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    worst = 0
    for entry in entries:
        result = run_workbook(entry, args.date, args.run, source, target, ledger)
        (OUT / "data" / f"{slug(entry['name'])}.json").write_text(
            json.dumps(result, indent=1, default=str)
        )
        diverging = sum(1 for ds in result["datasources"] if ds["status"] == "DIVERGE")
        print(
            f"{result['status']:<14} {entry['name']}"
            + (f"  ({diverging} datasource(s) differ)" if diverging else "")
        )
        if result["status"] in {"DIVERGE", "PENDING", "NOT REPOINTED"}:
            worst = 1
    importlib.import_module("render").render()
    print(f"console: {OUT / 'index.html'}")
    return worst


if __name__ == "__main__":
    sys.exit(main())
