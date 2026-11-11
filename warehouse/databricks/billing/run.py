"""Execute the direct conversion on the existing SQL warehouse."""
import json
from pathlib import Path

from ..sql import Warehouse
from ...teradata.bteq.parser import split


def run(client, script=None):
    statements = split(script or Path(__file__).with_name("direct.sql").read_text())
    receipts = []
    for index, statement in enumerate(statements, 1):
        result = client.execute(statement, step=f"direct-{index}")
        receipts.append({"step": index, "sql": statement, "statement_id": result["statement_id"]})
    return receipts


def main():
    receipts = run(Warehouse(act="prove", consumer="billing"))
    path = Path.home() / "dbx-evidence" / "direct_receipts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipts, indent=2))
    print(f"Completed {len(receipts)} direct statements; receipts: {path}")


if __name__ == "__main__":
    main()
