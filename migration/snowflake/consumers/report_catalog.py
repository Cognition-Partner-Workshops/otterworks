"""Write the report-service UBW report catalog from the thirty SSRS definitions.

report-service serves every report from one catalog entry with two queries: `sqlserver`, the
report's own DataSet query from source/reports/<report>.rdl, and `snowflake`, the same fields from
the REPORTS.<report> view with the report's ORDER BY. UBW_BACKEND picks one. Run this after a
report definition changes; gate/tests/test_report_catalog.py fails while the catalog is stale.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPORTS_DIR = HERE.parent / "source" / "reports"
CATALOG = ROOT / "services/report-service/src/main/resources/ubw/reports.json"
RDL_NS = {"r": "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"}
PARAMETER = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")
FILTER = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*@([A-Za-z_][A-Za-z0-9_]*)")
SOURCE = re.compile(r"\bFROM\s+([A-Za-z_]+\.[A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
ORDER_BY = re.compile(r"\bORDER\s+BY\s+(.+)$", re.IGNORECASE | re.DOTALL)


def report_entry(path: Path) -> dict:
    root = ET.parse(path).getroot()  # noqa: S314 - repository-owned report definitions
    command = (root.find(".//r:DataSet/r:Query/r:CommandText", RDL_NS).text or "").strip()
    fields = [
        element.text or ""
        for element in root.findall(".//r:DataSet/r:Fields/r:Field/r:DataField", RDL_NS)
    ]
    parameters = []
    for parameter in root.findall(".//r:ReportParameters/r:ReportParameter", RDL_NS):
        value = parameter.find("r:DefaultValue/r:Values/r:Value", RDL_NS)
        parameters.append(
            {"name": parameter.attrib["Name"], "default": None if value is None else value.text}
        )
    filters = {parameter: column for column, parameter in FILTER.findall(command)}
    order = ORDER_BY.search(command)
    snowflake = f"SELECT {', '.join(fields)} FROM REPORTS.{path.stem.upper()} WHERE "
    snowflake += " AND ".join(f"{filters[name]} = ?" for name in dict.fromkeys(filters))
    if order:
        snowflake += f" ORDER BY {order.group(1).strip()}"
    return {
        "name": path.stem,
        "fields": fields,
        "parameters": parameters,
        "sqlserver": {
            "source": SOURCE.search(command).group(1),
            "query": PARAMETER.sub("?", command),
            "parameters": PARAMETER.findall(command),
        },
        "snowflake": {
            "source": f"REPORTS.{path.stem.upper()}",
            "query": snowflake,
            "parameters": list(dict.fromkeys(filters)),
        },
    }


def build_catalog(reports_dir: Path = REPORTS_DIR) -> list[dict]:
    return [report_entry(path) for path in sorted(reports_dir.glob("rpt_*.rdl"))]


def render(catalog: list[dict]) -> str:
    return json.dumps({"reports": catalog}, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the catalog is stale")
    args = parser.parse_args()
    content = render(build_catalog())
    if args.check:
        if not CATALOG.is_file() or CATALOG.read_text(encoding="utf-8") != content:
            print(f"{CATALOG} is stale; run {Path(__file__).name}", file=sys.stderr)
            return 1
        return 0
    CATALOG.write_text(content, encoding="utf-8")
    print(f"Wrote {CATALOG.relative_to(ROOT)} ({len(content.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
