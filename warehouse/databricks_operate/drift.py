"""Fail closed when a landing feed changes its contract.

python -m warehouse.databricks_operate.drift check --landing <run-copy>
python -m warehouse.databricks_operate.drift seed --landing <run-copy>
The seed command refuses to modify checked-in landing files.
"""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class SchemaDrift(ValueError):
    pass


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def validate(rows, schema):
    if not rows:
        raise SchemaDrift("landing feed is empty")
    seen = set()
    for index, row in enumerate(rows, 1):
        if set(row) != set(schema):
            raise SchemaDrift(f"row {index}: added={sorted(set(row)-set(schema))} "
                              f"missing={sorted(set(schema)-set(row))}")
        for column, kind in schema.items():
            value = row[column]
            if kind == "integer" and type(value) is not int:
                raise SchemaDrift(f"row {index}: {column} is not an integer")
            if kind == "string" and not isinstance(value, str):
                raise SchemaDrift(f"row {index}: {column} is not a string")
            if kind == "decimal":
                try:
                    amount = Decimal(str(value))
                    if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
                        raise InvalidOperation()
                except (InvalidOperation, ValueError):
                    raise SchemaDrift(f"row {index}: {column} is not a finite cent amount") from None
            if kind not in {"integer", "string", "decimal"}:
                raise SchemaDrift("unsupported schema type: " + kind)
        key = row["invoice_id"]
        if key in seen:
            raise SchemaDrift(f"duplicate invoice_id {key}")
        seen.add(key)
    return {"rows": len(rows), "invoice_ids": sorted(seen),
            "amount": str(sum(Decimal(str(row["amount"])) for row in rows))}


def seed(path):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT):
        raise ValueError("copy the landing fixture outside the source directory before seeding")
    rows = read_rows(path)
    for row in rows:
        row["tax_region"] = "domestic" if row["currency"] == "USD" else "export"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "seed", "event"])
    parser.add_argument("--landing", type=Path, default=ROOT / "landing/invoices.jsonl")
    parser.add_argument("--schema", type=Path, default=ROOT / "schema.json")
    args = parser.parse_args()
    if args.action == "seed":
        seed(args.landing)
    elif args.action == "check":
        print(json.dumps(validate(read_rows(args.landing), json.loads(args.schema.read_text()))))
    else:
        # A real webhook trigger consumes this event after check fails; no credentials in payload.
        try:
            validate(read_rows(args.landing), json.loads(args.schema.read_text()))
        except SchemaDrift as error:
            print(json.dumps({"status": "firing", "run_token": "dbx-d1111", "act": "operate",
                              "alerts": [{"labels": {"alertname": "LandingSchemaDrift",
                              "run_token": "dbx-d1111", "severity": "warning"},
                              "annotations": {"summary": str(error)}}]}))
        else:
            raise SystemExit("landing is healthy; no alert event emitted")


if __name__ == "__main__":
    main()
