"""Generate dbt source declarations from the landing contract."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT.parent / "snowflake/landing_columns.yml"
TARGET = ROOT / "models/sources.yml"


def render():
    spec = yaml.safe_load(SPEC.read_text())
    return yaml.safe_dump({
        "version": 2,
        "sources": [
            {"name": area, "schema": f"RAW_{area.upper()}",
             "tables": [{"name": table, "columns": [{"name": name} for name in columns]}
                        for table, columns in tables.items()]}
            for area, tables in spec.items()
        ],
    }, sort_keys=False)


if __name__ == "__main__":
    TARGET.write_text(render())
