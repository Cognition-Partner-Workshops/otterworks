"""Run the rendered extraction SQL through the shared contract target."""
from datetime import date
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "consumers" / "contract-kit"))
from contract_client import execute

source = sys.stdin.read().rstrip()
match = re.search(r'^\.EXPORT REPORT FILE="([^"]+)"$', source, re.MULTILINE)
if not match:
    raise ValueError("missing report export")
export = match[1]
template = (ROOT.parent / "sql" / "partner_invoice_extract.bteq").read_text()
expected = template.replace("@EXTRACT_DATE_INT@", "1261109").replace("@EXPORT_FILE@", export)
if source != expected.rstrip():
    raise ValueError("contract received unexpected BTEQ query")
sql = source[source.index("LOCKING ROW FOR ACCESS"):source.index(";", source.index("LOCKING ROW FOR ACCESS"))]
as_of = os.environ.get("PARTNER_EXTRACT_AS_OF_DATE")
if as_of:
    sql = sql.replace("CURRENT_DATE - 1", f"DATE '{date.fromisoformat(as_of).isoformat()}' - 1", 1)
result = execute(sql, ROOT, os.environ.get("PARTNER_EXTRACT_QUERY", "partner-invoices"))
if result["columns"] != ["REPORT_ROW"] or any(len(row) != 1 for row in result["rows"]):
    raise ValueError("unexpected report shape")
with open(export, "w") as destination:
    for row in result["rows"]:
        destination.write(row[0] + "\n")
