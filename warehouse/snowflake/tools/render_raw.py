"""Render the RAW schema migration from the landing column contract."""

import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "migrations/V002__raw_tables.sql"


def render():
    spec = yaml.safe_load(_run_render((ROOT / "fixture_columns.yml").read_text()))
    statements = []
    for area, tables in spec.items():
        for table, columns in tables.items():
            definitions = [f"    {name} {kind}" for name, kind in columns.items()]
            definitions += ["    _SRC_FILE VARCHAR", "    _LOADED_AT TIMESTAMP_NTZ"]
            statements.append(
                f"CREATE TABLE RAW_{area.upper()}.{table} (\n"
                + ",\n".join(definitions)
                + _run_render("\n) COMMENT='__RUN_TOKEN__ raw landing';")
            )
    return "\n\n".join(statements) + "\n"


if __name__ == "__main__":
    TARGET.write_text(render())
