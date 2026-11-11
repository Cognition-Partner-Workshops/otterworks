"""Prove emulator inputs equal cpw.dbx_d1111_before on the columns this extract reads.

Order-independent: sha256 over the sorted canonical rows (strings trimmed, decimals
as plain strings, dates ISO). Needs the emulator (TD_PG_PORT) and Databricks secrets.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from databricks_warehouse import execute  # noqa: E402

TABLES = {
    "V_INVOICE_BASE": ["INVOICE_ID"],
    "INVOICE_HDR": ["INVOICE_ID", "CUSTOMER_ID", "INVOICE_NUMBER", "INVOICE_DT", "BILL_DT",
                    "TOTAL_AMOUNT", "TAX_AMOUNT", "CURRENCY_CD"],
    "CUSTOMER_ACCOUNT": ["CUSTOMER_ID", "ACCOUNT_NUMBER"],
    "PAYMENT": ["INVOICE_ID", "AMOUNT"],
}


def canonical(value):
    if value is None:
        return "\\N"
    return str(value).strip()


def digest(rows):
    lines = sorted("|".join(canonical(v) for v in row) for row in rows)
    return len(lines), hashlib.sha256("\n".join(lines).encode()).hexdigest()


def emulator(table, columns):
    sql = f"SEL {', '.join(columns)} FROM SFX_BILLING.{table}"
    output = subprocess.run([sys.executable, str(ROOT.parent / "contract-kit" / "bridge.py")],
                            input=sql, capture_output=True, text=True, check=True).stdout
    return json.loads(output)["rows"]


def main():
    ok = True
    for table, columns in TABLES.items():
        live = execute(f"SELECT {', '.join(columns)} FROM cpw.dbx_d1111_before.billing__{table.lower()}",
                       step="input-equality")
        before, old = digest(live["rows"]), digest(emulator(table, columns))
        match = before == old
        ok &= match
        print(json.dumps({"table": table, "before_count": before[0], "before_sha256": before[1],
                          "emulator_count": old[0], "emulator_sha256": old[1], "match": match,
                          "statement_id": live["statement_id"]}))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
