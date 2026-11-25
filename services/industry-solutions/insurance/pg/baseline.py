"""Pin the Oracle fixture's control figures as the golden baseline.

Run against the legacy system (after `make insurance-test` and
`make insurance-ledger-run`) before any target exists; reconcile.py checks
the live Oracle figures against this file and PostgreSQL against Oracle.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from common import control_metrics, oracle_connect

GOLDEN = Path(__file__).parent / "golden" / "oracle_baseline.json"


def main() -> int:
    with oracle_connect() as conn:
        metrics = control_metrics(conn)
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    t = metrics["tables"]
    print(f"wrote {GOLDEN}: {sum(v['rows'] for v in t.values())} rows across {len(t)} relations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
