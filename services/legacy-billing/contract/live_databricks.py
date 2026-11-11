"""Live source equality and AR aging parity. Never replays fixture rows."""
import hashlib
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "app"))
sys.path.insert(0, str(ROOT.parents[2] / "consumers" / "contract-kit"))
from bridge import execute as execute_old
from databricks_warehouse import execute
from databricks_receivables import DatabricksReceivablesWarehouse
from finance_warehouse import COLUMNS, SQL, TeradataReceivablesWarehouse

AS_OF = "2026-11-09"
TABLES = ("customer_account", "invoice_hdr", "payment", "v_account_invoices")
REQUIRED = ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID", "DATABRICKS_CATALOG", "DATABRICKS_RUN_TOKEN")


def canonical(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, Decimal)):
        return format(Decimal(value).normalize(), "f")
    return str(value).rstrip()


def fingerprint(rows):
    ordered = sorted(json.dumps([canonical(v) for v in row], separators=(",", ":")) for row in rows)
    return {"count": len(rows), "sha256": hashlib.sha256("\n".join(ordered).encode()).hexdigest()}


def normalized(rows):
    return [[Decimal(row[c]) if c in COLUMNS[4:] and row[c] is not None else row[c]
             for c in COLUMNS] for row in rows]


def run_contract():
    """Assert all inputs, team expectations, and every ordered output field."""
    evidence = {"as_of": AS_OF, "started_at": datetime.now().astimezone().isoformat(), "inputs": {}}
    for table in TABLES:
        baseline = execute(f"SELECT * FROM cpw.dbx_d1111_before.billing__{table}", step="input-equality")
        emulator = execute_old(f"SEL * FROM SFX_BILLING.{table}")
        old_rows = [[row[emulator["columns"].index(c)] for c in baseline["columns"]] for row in emulator["rows"]]
        target = execute(f"SELECT * FROM cpw.dbx_d1111_after.billing__{table}", step="target-input-equality")
        target_rows = [[row[target["columns"].index(c)] for c in baseline["columns"]] for row in target["rows"]]
        proof = {"emulator": fingerprint(old_rows), "baseline": fingerprint(baseline["rows"]),
                 "target": fingerprint(target_rows), "statement_ids": [baseline["statement_id"], target["statement_id"]]}
        evidence["inputs"][table] = proof
        same = proof["emulator"] == proof["baseline"] == proof["target"]
        print(f"INPUT {table}: emulator={proof['emulator']['count']} "
              f"baseline={proof['baseline']['count']} target={proof['target']['count']} "
              f"count+SHA256 {'MATCH' if same else 'MISMATCH'}", flush=True)
        assert proof["emulator"] == proof["baseline"] == proof["target"], f"input mismatch: {table}; {proof}"

    old_result = execute_old(SQL.replace("CURRENT_DATE", f"DATE '{AS_OF}'"))
    old_rows = [TeradataReceivablesWarehouse._map_row(row) for row in old_result["rows"]]
    old_values = normalized(old_rows)
    print("OLD PATH: original Teradata SQL via contract-kit bridge", flush=True)
    print(f"rows={len(old_rows)} SHA256={fingerprint(old_values)['sha256']}", flush=True)
    warehouse = DatabricksReceivablesWarehouse(AS_OF)
    print("NEW PATH: native Databricks SQL via SQL connector", flush=True)
    new_rows = warehouse.ar_aging()
    expected = json.loads((ROOT / "expected/ar-aging-databricks.json").read_text())
    new_values = normalized(new_rows)
    evidence["old"] = fingerprint(old_values)
    evidence["new"] = fingerprint(new_values)
    evidence["statement_id"] = warehouse.last_result["statement_id"]
    evidence["equal"] = old_values == new_values
    evidence["sums"] = {c: str(sum(Decimal(row[c]) for row in new_rows)) for c in expected["sums"]}
    evidence["finished_at"] = datetime.now().astimezone().isoformat()
    print(f"rows={len(new_rows)} SHA256={evidence['new']['sha256']}", flush=True)
    print(f"statement_id={evidence['statement_id']}", flush=True)
    assert old_result["columns"] == list(COLUMNS)
    assert warehouse.last_result["columns"] == list(COLUMNS[:-1]) + ["AMOUNT_DUE"]
    assert old_values == new_values, "ordered AR aging fields differ (including full precision OPEN_RATIO)"
    assert evidence["new"] == expected["result"]
    assert [r["ACCOUNT_NO"] for r in new_rows] == expected["keys"]
    for column, total in expected["sums"].items():
        assert Decimal(evidence["sums"][column]) == Decimal(total)
    for row in new_rows:
        assert sum(Decimal(row[c]) for c in COLUMNS[5:-1]) == Decimal(row["OPEN_BALANCE"])
    print(f"PASS: all ordered fields match; OPEN_BALANCE={evidence['sums']['OPEN_BALANCE']}", flush=True)
    if os.getenv("LEGACY_BILLING_EVIDENCE"):
        Path(os.environ["LEGACY_BILLING_EVIDENCE"]).write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


if __name__ == "__main__":
    missing = [key for key in REQUIRED if not os.getenv(key)]
    if missing:
        raise SystemExit("Live Databricks contract requires: " + ", ".join(missing))
    run_contract()
