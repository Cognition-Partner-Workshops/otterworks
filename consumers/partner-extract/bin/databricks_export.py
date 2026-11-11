"""BTEQ_BIN replacement: run the rendered partner extract natively on Databricks.

Reads the rendered BTEQ script on stdin (exactly as nightly_extract.sh renders it),
checks it is the canonical template, and writes the same report rows to the
.EXPORT file using sql/partner_invoice_extract.databricks.sql.
"""
from datetime import date
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def parse(source):
    template = (ROOT / "sql" / "partner_invoice_extract.bteq").read_text().rstrip()
    match = re.search(r'^\.EXPORT REPORT FILE="([^"]+)"$', source, re.MULTILINE)
    date_match = re.search(r"WHERE h\.BILL_DT = (1[0-9]{6})$", source, re.MULTILINE)
    if not match or not date_match:
        raise ValueError("missing report export or billing date")
    export, date_int = match[1], date_match[1]
    expected = template.replace("@EXTRACT_DATE_INT@", date_int).replace("@EXPORT_FILE@", export)
    if source.rstrip() != expected:
        raise ValueError("unexpected BTEQ script")
    value = int(date_int)
    extract_date = date(1900 + value // 10000, value // 100 % 100, value % 100)
    return export, extract_date.isoformat()


def main():
    export, extract_date = parse(sys.stdin.read())
    as_of = os.environ.get("PARTNER_EXTRACT_AS_OF_DATE") or None
    if as_of is not None:
        date.fromisoformat(as_of)
    from databricks_warehouse import execute

    sql = (ROOT / "sql" / "partner_invoice_extract.databricks.sql").read_text()
    result = execute(sql, {"extract_date": extract_date, "as_of_date": as_of},
                     step=os.environ.get("PARTNER_EXTRACT_STEP", "contract"))
    print(f"statement_id={result['statement_id']}", file=sys.stderr)
    log = os.environ.get("PARTNER_EXTRACT_STATEMENT_LOG")
    if log:
        with open(log, "a") as destination:
            destination.write(f"{result['statement_id']}\n")
    if result["columns"] != ["REPORT_ROW"] or any(len(row) != 1 or row[0] is None for row in result["rows"]):
        raise ValueError("unexpected report shape")
    with open(export, "w") as destination:
        for row in result["rows"]:
            destination.write(row[0] + "\n")


if __name__ == "__main__":
    main()
