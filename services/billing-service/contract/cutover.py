"""Run both real invoice read paths and print only aggregate contract evidence."""

import hashlib
import json
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from input_parity import input_equality
from warehouse_clients import ROOT, ContractConnection, EmulatorWarehouse

from app.export_invoices import export_invoices
from app.warehouse.databricks import DatabricksInvoiceWarehouse
from app.warehouse.teradata import TeradataInvoiceWarehouse


def main():
    started = datetime.now(UTC).isoformat()
    run_date = date(2026, 11, 10)
    print("BILLING INVOICE EXPORT: live old/new cutover", flush=True)
    print("Run date 2026-11-10; BILL_DT 2026-11-09; seed BUSINESS_DATE=20261109", flush=True)
    inputs = input_equality()
    for table, proof in inputs.items():
        print(
            f"INPUT {table}: {proof['emulator_count']} rows; hash {proof['emulator_hash']} MATCH",
            flush=True,
        )
        print("  statement_id:", proof["statement_id"], flush=True)
    os.environ["WAREHOUSE_CONTRACT_TARGET"] = "teradata-emulator"
    connection = ContractConnection(EmulatorWarehouse())
    old = TeradataInvoiceWarehouse(connect=lambda **_kwargs: connection)
    new = DatabricksInvoiceWarehouse()
    with TemporaryDirectory() as directory:
        old_file = Path(directory) / "old.csv"
        new_file = Path(directory) / "new.csv"
        old_count = export_invoices(old, run_date, old_file)
        print(
            f"OLD PATH: Teradata SQL -> contract-kit Runner -> PostgreSQL: {old_count} rows",
            flush=True,
        )
        new_count = export_invoices(new, run_date, new_file)
        print(
            f"NEW PATH: native SQL -> Databricks SQL connector -> after: {new_count} rows",
            flush=True,
        )
        print("  statement_id:", new.last_result["statement_id"], flush=True)
        assert old_file.read_bytes() == new_file.read_bytes(), "CSV byte mismatch"
        csv_hash = hashlib.sha256(new_file.read_bytes()).hexdigest()
    expected = json.loads((ROOT / "expected/invoice-export.json").read_text())
    rows = new.last_result["rows"]
    assert old_count == new_count == expected["row_count"]
    assert [row[0] for row in rows] == expected["keys"]
    sums = {
        column: str(sum((Decimal(str(row[index])) for row in rows), Decimal(0)))
        for column, index in (("AMOUNT_DUE", 5), ("TAX_AMT", 6), ("OPEN_BALANCE", 7))
    }
    assert sums == expected["sums"]
    evidence = {
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "run_date": str(run_date),
        "inputs": inputs,
        "row_count": new_count,
        "sums": sums,
        "csv_sha256": csv_hash,
        "statement_id": new.last_result["statement_id"],
        "csv_bytes_equal": True,
    }
    (ROOT / "cutover.local.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print("TOTALS:", json.dumps(sums), flush=True)
    print("PASS: all fields, contract keys/sums and CSV bytes equal. SHA256:", csv_hash, flush=True)
    return evidence


if __name__ == "__main__":
    main()
