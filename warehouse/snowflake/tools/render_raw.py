"""Render the RAW schema migration from the landing column contract."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "migrations/V002__raw_tables.sql"


def render():
    spec = yaml.safe_load((ROOT / "fixture_columns.yml").read_text())
    statements = []
    for area, tables in spec.items():
        for table, columns in tables.items():
            definitions = [f"    {name} {kind}" for name, kind in columns.items()]
            definitions += ["    _SRC_FILE VARCHAR", "    _LOADED_AT TIMESTAMP_NTZ"]
            statements.append(
                f"CREATE TABLE RAW_{area.upper()}.{table} (\n"
                + ",\n".join(definitions)
                + "\n) COMMENT='sfx-d1110 raw landing';"
            )
    return "\n\n".join(statements) + "\n"


if __name__ == "__main__":
    TARGET.write_text(render())
