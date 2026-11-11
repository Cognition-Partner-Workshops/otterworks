"""Record the old Teradata read path on the emulator seeded to match the live baseline.

Usage (emulator seeded with ROWS_PER_TABLE=2000 BUSINESS_DATE=20261109, TD_PG_PORT set):
    python -m contract.old_path
Writes recorded/teradata-baseline/<query>.json (exact rows) and expected/baseline/<query>.json.
CURRENT_DATE is pinned to CONTRACT_AS_OF_DATE (default 2026-11-09) on both paths.
"""
from decimal import Decimal
import json
import os
import subprocess
import sys

from contract.warehouse import AS_OF_DATE, ROOT, pin_as_of
from semantic import queries

BRIDGE = ROOT.parents[1] / "contract-kit" / "bridge.py"
KEYS = {"overdue_accounts": ("ACCOUNT_NO", "OVERDUE_BALANCE")}


def main():
    for name, sql in sorted(queries().items()):
        result = subprocess.run([os.getenv("CONTRACT_KIT_PYTHON", sys.executable), str(BRIDGE)],
                                input=pin_as_of(sql), text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        data = json.loads(result.stdout)
        recorded = {"query": name, "as_of": AS_OF_DATE, **data}
        (ROOT / "recorded" / "teradata-baseline" / f"{name}.json").write_text(json.dumps(recorded, indent=2) + "\n")
        key, amount = KEYS.get(name, ("LABEL", "AMOUNT"))
        k, a = data["columns"].index(key), data["columns"].index(amount)
        expected = {"query": name, "row_count": len(data["rows"]),
                    "sums": {amount: str(sum((Decimal(str(r[a])) for r in data["rows"]), Decimal("0")))},
                    "key_column": key, "keys": [str(r[k]).strip() for r in data["rows"]]}
        (ROOT / "expected" / "baseline" / f"{name}.json").write_text(json.dumps(expected, indent=2) + "\n")
        print(f"{name}: {len(data['rows'])} rows, {amount}={expected['sums'][amount]}")


if __name__ == "__main__":
    main()
