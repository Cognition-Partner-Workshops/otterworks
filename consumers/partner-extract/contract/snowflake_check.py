"""Read-only native and report-format checks for the live extract."""
import csv
from decimal import Decimal
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
from snowflake_export import connect, query

output, work = map(Path, sys.argv[1:])
with output.open(newline="") as source:
    header, *rows, trailer = list(csv.reader(source))
expected = json.loads((ROOT / "contract/expected/partner-invoices.json").read_text())
with (ROOT / "contract/expected/partner-invoices.csv").open(newline="") as source:
    assert header == next(csv.reader(source))
keys = [row[0] for row in rows]
assert len(keys) == len(set(keys))
assert keys == sorted(keys, key=lambda key: (key.upper(), key))
assert set(expected["keys"]) <= set(keys)
assert len(expected["keys"]) == 267
assert sorted(keys)[:267] == expected["keys"]
assert all(row[2] == "2026-11-09" for row in rows)
assert {row[6] for row in rows} <= {"USD", "EUR", "GBP", "CAD", "AUD", "NOK"}
sums = [sum((Decimal(row[i]) for row in rows), Decimal(0)) for i in (3, 4, 5)]
assert trailer == ["TRAILER", str(len(rows)), str(sums[0])]

with connect() as connection, connection.cursor() as cursor:
    query(cursor, (ROOT / "sql/partner_invoice_extract.sql").read_text(),
          {"extract_date": "2026-11-09"})
    assert [column[0] for column in cursor.description] == ["REPORT_ROW"]
    raw_rows = [row[0] for row in cursor]
    pattern = re.compile(
        r"INV-[A-Za-z0-9-]+,(?:A[0-9]+|ACC-[0-9]+),2026-11-09,"
        r"-?[0-9]+\.[0-9]{2},-?[0-9]+\.[0-9]{2},-?[0-9]+\.[0-9]{2},[A-Z]{3}"
    )
    assert all(pattern.fullmatch(row) for row in raw_rows)
    query(cursor, """
SELECT COUNT(*), SUM(h.TOTAL_AMOUNT), SUM(ZEROIFNULL(h.TAX_AMOUNT)),
       SUM(h.TOTAL_AMOUNT - ZEROIFNULL(p.PAID))
FROM SFX_D1110_AFTER.RAW_BILLING.INVOICE_HDR h
JOIN SFX_D1110_AFTER.RAW_BILLING.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = h.CUSTOMER_ID
LEFT JOIN (
  SELECT INVOICE_ID, SUM(AMOUNT) AS PAID
  FROM SFX_D1110_AFTER.RAW_BILLING.PAYMENT GROUP BY INVOICE_ID
) p ON p.INVOICE_ID = h.INVOICE_ID
WHERE h.BILL_DT = TO_DATE(%(extract_date)s)
  AND h.INVOICE_DT >= DATE '2020-01-01'
  AND h.BILL_DT <= DATEADD(day, -1, CURRENT_DATE())
""", {"extract_date": "2026-11-09"})
    count, *native_sums = cursor.fetchone()
    assert count == len(rows), (count, len(rows))
    assert [Decimal(value) for value in native_sums] == sums, (native_sums, sums)

recorded = json.loads((ROOT / "contract/recorded/teradata/partner-invoices.json").read_text())
for label, report in (("teradata", [row[0] for row in recorded["rows"]]),
                      ("snowflake", raw_rows)):
    raw = work / (label + "-raw.csv")
    normalized = work / (label + "-normalized.csv")
    raw.write_text("".join(row + "\n" for row in report))
    subprocess.run(["bash", str(ROOT / "bin/postprocess.sh"), str(raw), str(normalized)], check=True)
    if label == "snowflake":
        assert normalized.read_bytes() == output.read_bytes()
print("PASS Teradata and Snowflake report formats accepted (.00 and 0.00 normalized)")
print(f"PASS snowflake partner-invoices: rows={len(rows)} amount_due={sums[0]} tax_amt={sums[1]} open_balance={sums[2]}")
