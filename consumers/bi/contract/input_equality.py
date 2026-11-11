"""Prove the emulator's input rows equal cpw.dbx_d1111_before (count + order-independent hash).

Usage (TD_PG_PORT and DATABRICKS_* set): python -m contract.input_equality
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import subprocess
import sys

from contract.warehouse import ROOT

sys.path.insert(0, str(ROOT.parent))
import databricks_warehouse  # noqa: E402

BRIDGE = ROOT.parents[1] / "contract-kit" / "bridge.py"
TABLES = ["INVOICE_HDR", "V_INVOICE_REVENUE", "CUSTOMER_ACCOUNT", "PAYMENT", "GL_ACCOUNT", "GL_JOURNAL_LINE"]


def canonical(value):
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    try:
        return format(Decimal(str(value)).normalize(), "f")
    except InvalidOperation:
        return str(value)


def digest(columns, rows):
    order = sorted(range(len(columns)), key=lambda i: columns[i].lower())
    total = sum(int(hashlib.md5("|".join(canonical(r[i]) for i in order).encode()).hexdigest()[:15], 16)
                for r in rows)
    return [columns[i].lower() for i in order], len(rows), str(total)


def main(step="inputs"):
    results, ok = [], True
    for table in TABLES:
        emulator = subprocess.run([os.getenv("CONTRACT_KIT_PYTHON", sys.executable), str(BRIDGE)],
                                  input=f"SEL * FROM SFX_BILLING.{table}", text=True,
                                  capture_output=True, check=True)
        em = json.loads(emulator.stdout)
        live = databricks_warehouse.execute_with_id(
            f"SELECT * FROM cpw.dbx_d1111_before.billing__{table.lower()}", step=step)
        e, b = digest(em["columns"], em["rows"]), digest(live["columns"], live["rows"])
        match = e == b
        ok &= match
        results.append({"table": table, "emulator_count": e[1], "before_count": b[1],
                        "emulator_hash": e[2], "before_hash": b[2], "match": match,
                        "statement_id": live["statement_id"]})
        print(json.dumps(results[-1]))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(*sys.argv[1:]) else 1)
