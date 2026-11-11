"""Record the old read path (Teradata SQL on the emulator) for the live Databricks comparison.

Seed the emulator to match cpw.dbx_d1111_before first (ROWS_PER_TABLE=2000,
BUSINESS_DATE=20261109), then: CONTRACT_AS_OF=2026-11-09 python -m contract.record_baseline
"""
import json
import os

from contract.warehouse import BASELINE, ROOT, execute_contract
from finance_nb.databricks_queries import pin_teradata
from finance_nb.queries import extract_queries


def main():
    as_of = os.environ["CONTRACT_AS_OF"]
    BASELINE.mkdir(parents=True, exist_ok=True)
    for name, sql in sorted(extract_queries().items()):
        os.environ["WAREHOUSE_CONTRACT_TARGET"] = "teradata-emulator"
        data = execute_contract(pin_teradata(sql, as_of), ROOT, name)
        data = {"query": name, "as_of": as_of, "columns": data["columns"], "rows": data["rows"]}
        (BASELINE / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
        print(name, len(data["rows"]))


if __name__ == "__main__":
    main()
