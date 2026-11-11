"""Execute a billing conversion checkpoint on the existing SQL warehouse."""
import argparse
import json
from pathlib import Path
import re

from ..sql import Warehouse
from ...teradata.bteq.parser import split


def run(client, script=None, *, version="direct", inputs_only=False):
    statements = split(script or Path(__file__).with_name(version + ".sql").read_text())
    receipts = []
    for index, statement in enumerate(statements, 1):
        mutation = re.match(r"(?:CREATE(?: OR REPLACE)? (?:TABLE|VIEW|FUNCTION)|INSERT INTO|MERGE INTO|UPDATE|DELETE FROM|DROP (?:TABLE|VIEW|FUNCTION)(?: IF EXISTS)?)\s+([\w.]+)", statement, re.I)
        if mutation and not mutation[1].startswith("cpw.dbx_d1111_after.billing__"):
            raise ValueError("conversion may only write billing-owned after objects")
        writes = re.findall(r"(?:TABLE|VIEW|FUNCTION|INTO|UPDATE|FROM)\s+(cpw\.dbx_d1111_after\.\w+)", statement, re.I)
        if any(not name.startswith("cpw.dbx_d1111_after.billing__") for name in writes):
            raise ValueError("conversion may only reference billing-owned after objects")
        if inputs_only and not re.match(r"CREATE OR REPLACE (?:TABLE|FUNCTION) cpw\.dbx_d1111_after\.billing__in_", statement):
            continue
        result = client.execute(statement, step=f"{version}-{index}")
        receipts.append({"step": index, "sql": statement, "statement_id": result["statement_id"]})
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=["direct", "fixed"], default="direct")
    parser.add_argument("--inputs-only", action="store_true")
    args = parser.parse_args()
    receipts = run(Warehouse(act="prove", consumer="billing"), version=args.version, inputs_only=args.inputs_only)
    path = Path.home() / "dbx-evidence" / (args.version + ("_inputs" if args.inputs_only else "") + "_receipts.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipts, indent=2))
    print(f"Completed {len(receipts)} {args.version} statements; receipts: {path}")


if __name__ == "__main__":
    main()
