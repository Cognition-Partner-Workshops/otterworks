"""Run the rendered extraction SQL through the shared contract target."""
from pathlib import Path
from datetime import date
import re
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "consumers" / "contract-kit"))
from contract_client import execute

extract_date = date.fromisoformat(sys.argv[1])
export_path = sys.argv[2]
date_int = (extract_date.year - 1900) * 10000 + extract_date.month * 100 + extract_date.day
template = (ROOT / "teradata" / "partner_invoice_extract.bteq").read_text()
source = template.replace("@EXTRACT_DATE_INT@", str(date_int)).replace("@EXPORT_FILE@", export_path).rstrip()
match = re.search(r'^\.EXPORT REPORT FILE="([^"]+)"$', source, re.MULTILINE)
if not match:
    raise ValueError("missing report export")
export = match[1]
expected = template.replace("@EXTRACT_DATE_INT@", "1261109").replace("@EXPORT_FILE@", export)
if source != expected.rstrip():
    raise ValueError("contract received unexpected BTEQ query")
sql = source[source.index("LOCKING ROW FOR ACCESS"):source.index(";", source.index("LOCKING ROW FOR ACCESS"))]
result = execute(sql, ROOT, "partner-invoices")
if result["columns"] != ["REPORT_ROW"] or any(len(row) != 1 for row in result["rows"]):
    raise ValueError("unexpected report shape")
with open(export, "w") as destination:
    for row in result["rows"]:
        destination.write(row[0] + "\n")
